"""Plan metrics. Every number comes from contracts.costs and contracts.rules."""
from __future__ import annotations

from contracts import costs, rules
from contracts.models import Assignment, Metrics, Mode, Plan, RiskKind, Scenario, Work


def _live(plan: Plan, scenario: Scenario) -> list[tuple[Work, Assignment]]:
    works = {w.work_id: w for w in scenario.works}
    return [(works[a.work_id], a) for a in plan.assignments if a.work_id in works and not works[a.work_id].done]


def plan_cost_inr(plan: Plan, scenario: Scenario) -> int:
    live = _live(plan, scenario)
    total = sum(costs.option_for(w, a.mode).cost_inr + costs.delay_cost_inr(max(0, a.start_day - w.requested_start))
                for w, a in live)
    in_group: dict[str, set[str]] = {}
    for _, a in live:
        if a.shared_group:
            in_group.setdefault(a.shared_group, set()).add(a.work_id)
    for g in scenario.parallel_groups:
        if set(g.work_ids) <= in_group.get(g.group_id, set()):
            total -= g.saving_inr
    return total


def lane_closure_hours_total(plan: Plan, scenario: Scenario) -> float:
    segments_by_id = {s.segment_id: s for s in scenario.segments}
    total = 0.0
    shared: dict[str, float] = {}
    for w, a in _live(plan, scenario):
        hours = costs.lane_closure_hours(w, a.mode, a.end_day - a.start_day + 1, segments_by_id)
        if a.shared_group:
            shared[a.shared_group] = max(shared.get(a.shared_group, 0.0), hours)
        else:
            total += hours
    return total + sum(shared.values())


def _dust_score(plan: Plan, scenario: Scenario) -> float:
    air_days = {d for win in scenario.risk_windows if win.kind == RiskKind.air
                for d in range(win.start_day, win.end_day + 1)}
    score = 0.0
    for w, a in _live(plan, scenario):
        if a.mode != Mode.open_cut:
            continue
        dust = costs.option_for(w, a.mode).dust
        score += sum(dust * (2.0 if d in air_days else 1.0) for d in range(a.start_day, a.end_day + 1))
    return round(score, 1)


def compute_metrics(plan: Plan, scenario: Scenario) -> Metrics:
    live = _live(plan, scenario)
    cuts = {a.shared_group or a.work_id for _, a in live if a.mode == Mode.open_cut}
    digs = list(rules.digs_per_segment(scenario, plan).values())
    late = [max(0, a.start_day - w.requested_start) for w, a in live]
    return Metrics(
        plan_id=plan.plan_id,
        excavations=len(cuts),
        digs_per_road=round(sum(digs) / len(digs), 1) if digs else 0.0,
        lane_closure_hours=round(lane_closure_hours_total(plan, scenario), 1),
        trench_hours_in_rain=rules.rain_trench_hours(scenario, plan),
        clashes=rules.clash_count(scenario, plan),
        days_late=round(sum(late) / len(late), 1) if late else 0.0,
        cost_inr=plan_cost_inr(plan, scenario),
        dust_score=_dust_score(plan, scenario),
    )
