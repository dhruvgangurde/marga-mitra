"""Fix the dates and methods of every work, then explain each one in plain words."""
from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime, timedelta

from ortools.sat.python import cp_model

from contracts import costs
from contracts.fakes import tiny_scenario
from contracts.models import (
    Assignment,
    Dept,
    Mode,
    Plan,
    PlanVariant,
    RiskKind,
    RiskWindow,
    Scenario,
    SolveConstraints,
    Work,
)
from solver.baselines import naive_plan
from solver.metrics import compute_metrics
from solver.model import build, protected_on


def day_text(scenario: Scenario, day: int) -> str:
    d = scenario.start_date + timedelta(days=day)
    return f"{d.day} {d:%b}"


def days_text(scenario: Scenario, start: int, end: int) -> str:
    s, e = (scenario.start_date + timedelta(days=x) for x in (start, end))
    if start == end:
        return day_text(scenario, start)
    if s.month == e.month:
        return f"{s.day}–{e.day} {e:%b}"
    return f"{day_text(scenario, start)} – {day_text(scenario, end)}"


def _asked_overlap(scenario: Scenario, work: Work, kind: RiskKind) -> RiskWindow | None:
    """The first window of this kind on the work's roads that the asked days run into."""
    end = work.requested_start + work.modes[0].duration_days - 1
    for win in scenario.risk_windows:
        if (win.kind == kind and set(win.segment_ids) & set(work.segment_ids)
                and win.start_day <= end and work.requested_start <= win.end_day):
            return win
    return None


def reason_for(work: Work, a: Assignment, scenario: Scenario, constraints: SolveConstraints,
               plan_assignments: list[Assignment]) -> str:
    works = {w.work_id: w for w in scenario.works}
    if work.is_emergency:
        return "Emergency: started at once."
    if a.shared_group:
        others = [b.work_id for b in plan_assignments if b.shared_group == a.shared_group and b.work_id != work.work_id]
        names = " and ".join(f"{works[o].dept.value.capitalize()} {o}" for o in others)
        return f"Shares one trench with {names}."
    if a.mode == Mode.trenchless:
        if protected_on(scenario, work, a.start_day):
            return f"Trenchless: {work.road_name} is a protected road."
        return "Trenchless: no road cut."
    if a.start_day == work.requested_start:
        return "As the department asked."
    later = a.start_day > work.requested_start
    if constraints.use_risk and work.modes[0].mode == Mode.open_cut and _asked_overlap(scenario, work, RiskKind.rain):
        return f"Moved {'after' if later else 'before'} the rain: the road is low-lying."
    event = _asked_overlap(scenario, work, RiskKind.event) if constraints.use_risk else None
    if event:
        return f"Moved to keep the road free for {event.label}."
    if work.dept == Dept.roads:
        return "Resurfaces after every dig on the road."
    if later and any(b.shared_group and b.work_id != work.work_id and b.end_day < a.start_day
                     and set(works[b.work_id].segment_ids) & set(work.segment_ids) for b in plan_assignments):
        return "Starts after the shared trench is closed."
    if work.work_id in constraints.pinned_start or work.work_id in constraints.min_start:
        return "Dates agreed in the negotiation."
    return f"Moved to avoid a clash on {work.road_name}."


def _load(seed: int) -> Scenario:
    """The real test case and its windows when Track 4's modules are merged, else the small test scenario."""
    try:
        from data.scenario import generate_scenario
    except ModuleNotFoundError:
        print("Using the small test scenario (data.scenario is not merged yet).")
        scenario = tiny_scenario(seed)
    else:
        scenario = generate_scenario(seed)
    try:
        from risk.windows import compute_risk_windows
    except ModuleNotFoundError:
        return scenario
    return scenario.model_copy(update={"risk_windows": compute_risk_windows(scenario, "fixture")})


def _summary(plan: Plan, scenario: Scenario) -> list[str]:
    last = scenario.horizon_days - 1
    lines = [f"Test case {scenario.seed} · {day_text(scenario, 0)} to {day_text(scenario, last)} · {plan.plan_id}"]
    for a in plan.assignments:
        mode = "open cut" if a.mode == Mode.open_cut else "trenchless"
        lines.append(f"{a.work_id}  {days_text(scenario, a.start_day, a.end_day)}  {mode}  {a.shared_group or '-'}  "
                     f"{a.reason}")
    lines += plan.notes
    m = compute_metrics(plan, scenario)
    lines.append(f"Digs per road {m.digs_per_road} · lane-closure hours {round(m.lane_closure_hours)} · "
                 f"clashes {m.clashes} · trench-hours in rain {round(m.trench_hours_in_rain)} · "
                 f"days late {m.days_late} · cost {costs.inr(m.cost_inr)}")
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print a plan for one test case in plain words.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--naive", action="store_true", help="print the old-way plan instead")
    parser.add_argument("--share", action="append", default=[], metavar="GROUP_ID", help="an accepted shared trench")
    parser.add_argument("--no-risk", action="store_true", help="ignore rain, air and event windows")
    args = parser.parse_args(argv)
    scenario = _load(args.seed)
    if args.naive:
        plan = naive_plan(scenario)
    else:
        plan = solve(scenario, SolveConstraints(shared_groups=args.share, use_risk=not args.no_risk))
    print("\n".join(_summary(plan, scenario)))


def solve(scenario: Scenario, constraints: SolveConstraints, variant: PlanVariant = PlanVariant.orchestrated) -> Plan:
    t0 = time.perf_counter()
    built = build(scenario, constraints)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = scenario.seed
    # the deterministic budget decides, so the same inputs give the same plan; the wall clock is only a safety net
    solver.parameters.max_deterministic_time = constraints.time_limit_s
    solver.parameters.max_time_in_seconds = constraints.time_limit_s * 4
    status = solver.solve(built.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(f"No plan found: {solver.status_name(status)}")

    picked: dict[str, Assignment] = {}
    for (work_id, mode, start), (x, duration) in built.choices.items():
        if solver.boolean_value(x):
            picked[work_id] = Assignment(work_id=work_id, start_day=start, end_day=start + duration - 1, mode=mode)
    for (group_id, start), (t, duration) in built.trenches.items():
        if solver.boolean_value(t):
            for work_id in built.groups[group_id].work_ids:
                picked[work_id] = Assignment(work_id=work_id, start_day=start, end_day=start + duration - 1,
                                             mode=Mode.open_cut, shared_group=group_id)

    assignments: list[Assignment] = []
    unplanned: list[str] = []
    notes: list[str] = []
    for work in scenario.works:
        if work.done:
            continue
        if work.work_id in picked:
            assignments.append(picked[work.work_id])
        else:
            unplanned.append(work.work_id)
            notes.append(f"{work.work_id} could not be planned between {day_text(scenario, work.earliest_start)} "
                         f"and {day_text(scenario, work.latest_end)}.")
    works = {w.work_id: w for w in scenario.works}
    assignments = [a.model_copy(update={"reason": reason_for(works[a.work_id], a, scenario, constraints, assignments)})
                   for a in assignments]
    return Plan(plan_id=f"P-{scenario.seed}-{variant.value}", seed=scenario.seed, variant=variant,
                created_at=datetime.now(UTC), assignments=assignments, unplanned=unplanned, notes=built.notes + notes,
                objective=solver.objective_value, solve_ms=int((time.perf_counter() - t0) * 1000))


if __name__ == "__main__":
    main()
