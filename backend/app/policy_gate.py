"""The rules check: six checks on a plan and the approval tier. Pure: no database, no settings."""
from collections import defaultdict

from contracts import costs, rules
from contracts.models import (
    Assignment,
    ConflictKind,
    Dept,
    Mode,
    Plan,
    PolicyResult,
    RiskKind,
    RuleCheck,
    Scenario,
    Work,
)


def plan_cost_inr(plan: Plan, scenario: Scenario) -> int:
    """Same formula as the scheduler track's metrics: dig, restoration and delay, minus shared-trench savings."""
    works = {w.work_id: w for w in scenario.works}
    total = sum(costs.option_for(works[a.work_id], a.mode).cost_inr
                + costs.delay_cost_inr(max(0, a.start_day - works[a.work_id].requested_start))
                for a in plan.assignments if a.work_id in works and not works[a.work_id].done)
    groups = {a.work_id: a.shared_group for a in plan.assignments}
    return total - sum(g.saving_inr for g in scenario.parallel_groups
                       if all(groups.get(w) == g.group_id for w in g.work_ids))


def _ids(ids: set[str] | list[str]) -> str:
    return ", ".join(sorted(ids))


def _live(plan: Plan, works: dict[str, Work]) -> list[Assignment]:
    return [a for a in plan.assignments if a.work_id in works and not works[a.work_id].done]


def _window_hits(scenario: Scenario, live: list[Assignment], works: dict[str, Work], kind: RiskKind,
                 open_cut_only: bool) -> dict[str, set[str]]:
    """Window label -> works whose days overlap that window on one of their segments."""
    hits: dict[str, set[str]] = defaultdict(set)
    for win in scenario.risk_windows:
        if win.kind != kind:
            continue
        for a in live:
            if open_cut_only and a.mode != Mode.open_cut:
                continue
            if set(works[a.work_id].segment_ids) & set(win.segment_ids) and a.start_day <= win.end_day and win.start_day <= a.end_day:
                hits[win.label].add(a.work_id)
    return hits


def _check(name: str, bad: str, severity: str, ok: str) -> RuleCheck:
    return RuleCheck(name=name, severity=severity, detail=bad) if bad else RuleCheck(name=name, severity="ok", detail=ok)


def _checks(plan: Plan, scenario: Scenario) -> list[RuleCheck]:
    works = {w.work_id: w for w in scenario.works}
    live = _live(plan, works)
    clashes = rules.find_clashes(scenario, plan, include_risk=False)

    protected = {i for c in clashes if c.kind == ConflictKind.protected_road for i in c.work_ids}
    low_deposit = {a.work_id for a in live
                   if works[a.work_id].deposit_inr < costs.deposit_inr(works[a.work_id].dept, works[a.work_id].length_m, a.mode)}
    rain = _window_hits(scenario, live, works, RiskKind.rain, open_cut_only=True)
    air = _window_hits(scenario, live, works, RiskKind.air, open_cut_only=True)
    events = _window_hits(scenario, live, works, RiskKind.event, open_cut_only=False)
    order: dict[str, set[str]] = defaultdict(set)
    for c in clashes:
        if c.kind == ConflictKind.order:
            road = next(i for i in c.work_ids if works[i].dept == Dept.roads)
            order[road].update(i for i in c.work_ids if i != road)

    return [
        _check("protected_roads", f"{_ids(protected)} would cut a protected road" if protected else "", "fail",
               "No protected road is dug"),
        _check("deposits", f"{_ids(low_deposit)} hold a smaller deposit than the rules ask for" if low_deposit else "",
               "warn", "Every deposit is held until the repair is verified"),
        _check("rain", "; ".join(f"{_ids(ids)} have an open trench during {label}" for label, ids in rain.items()),
               "warn", "No open trench during heavy rain"),
        _check("air", "; ".join(f"{_ids(ids)} have an open cut during {label}" for label, ids in air.items()),
               "warn", "No open cut on poor-air days"),
        _check("events", "; ".join(f"{_ids(ids)} are on the route of {label}" for label, ids in events.items()),
               "fail", "No work on an event route"),
        _check("order", "; ".join(f"{road} would resurface before {_ids(ids)} finishes" for road, ids in sorted(order.items())),
               "fail", "Resurfacing comes after every dig"),
    ]


def _keys(plan: Plan) -> dict[str, tuple]:
    return {a.work_id: (a.start_day, a.end_day, a.mode, a.shared_group) for a in plan.assignments}


def _works_changed(plan: Plan, base: Plan | None) -> set[str]:
    if base is None:
        return {a.work_id for a in plan.assignments}
    new, old = _keys(plan), _keys(base)
    return {w for w in new.keys() | old.keys() if new.get(w) != old.get(w)}


def check_policy(plan: Plan, base: Plan | None, scenario: Scenario) -> PolicyResult:
    checks = _checks(plan, scenario)
    changed = _works_changed(plan, base)
    delta = plan_cost_inr(plan, scenario) - plan_cost_inr(base, scenario) if base else 0
    depts = {w.dept for w in scenario.works if w.work_id in changed}
    tier = next((t["name"] for t in costs.policy()["approvals"]["tiers"]
                 if len(changed) <= t["max_works_changed"] and abs(delta) <= t["max_cost_delta_inr"]
                 and (len(depts) <= 1 or not t["single_department"])), "commissioner")
    return PolicyResult(plan_id=plan.plan_id, passed=all(c.severity != "fail" for c in checks), checks=checks,
                        tier=tier, works_changed=len(changed), cost_delta_inr=delta)
