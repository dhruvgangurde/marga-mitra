from datetime import date

from backend.app.policy_gate import check_policy, plan_cost_inr
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import Plan, RiskKind, RiskWindow

NAMES = ["protected_roads", "deposits", "rain", "air", "events", "order"]


def _moved(plan: Plan, **moves: tuple[int, int, str | None]) -> Plan:
    """moves: work id with '-' as '_' -> (start, end, shared_group)."""
    out = []
    for a in plan.assignments:
        m = moves.get(a.work_id.replace("-", "_"))
        out.append(a.model_copy(update={"start_day": m[0], "end_day": m[1], "shared_group": m[2]}) if m else a)
    return plan.model_copy(update={"assignments": out})


def _severity(result, name: str) -> str:
    return next(c.severity for c in result.checks if c.name == name)


def test_old_way_cost():
    s = tiny_scenario(1)
    assert plan_cost_inr(fake_naive_plan(s), s) == 4_988_000


def test_old_way_fails_on_order():
    s = tiny_scenario(1)
    r = check_policy(fake_naive_plan(s), None, s)
    assert [c.name for c in r.checks] == NAMES
    assert [c.severity for c in r.checks] == ["ok", "ok", "warn", "ok", "ok", "fail"]
    assert (r.passed, r.works_changed, r.cost_delta_inr, r.tier) == (False, 4, 0, "ward_engineer")


def test_one_day_move_is_auto():
    s = tiny_scenario(1)
    old = fake_naive_plan(s)
    r = check_policy(_moved(old, G_001=(10, 13, None)), old, s)
    assert (r.works_changed, r.cost_delta_inr, r.tier) == (1, 2000, "auto")


def test_six_day_move_needs_department_officer():
    s = tiny_scenario(1)
    old = fake_naive_plan(s)
    r = check_policy(_moved(old, G_001=(15, 18, None)), old, s)
    assert (r.cost_delta_inr, r.tier) == (12000, "department_officer")


def test_shared_trench_plan_passes():
    s = tiny_scenario(1)
    old = fake_naive_plan(s)
    plan = _moved(old, W_001=(14, 18, "G1"), T_001=(14, 18, "G1"), G_001=(13, 16, None), R_001=(19, 21, None))
    r = check_policy(plan, old, s)
    assert r.passed and [c.severity for c in r.checks] == ["ok"] * 6
    assert (r.works_changed, r.cost_delta_inr, r.tier) == (4, -624000, "ward_engineer")


def test_event_route_fails():
    s = tiny_scenario(1)
    s.risk_windows.append(RiskWindow(window_id="EV-1", kind=RiskKind.event, start_day=9, end_day=9, segment_ids=["S-0003"],
                                     value=0, source="event", label="Procession, 11 Nov"))
    r = check_policy(fake_naive_plan(s), None, s)
    assert _severity(r, "events") == "fail"
    assert "G-001, R-001 are on the route of Procession, 11 Nov" == next(c.detail for c in r.checks if c.name == "events")


def test_protected_road_fails_unless_emergency():
    s = tiny_scenario(1)
    s.segments[2] = s.segments[2].model_copy(update={"protected_until": date(2029, 1, 1)})
    old = fake_naive_plan(s)
    only_gas = old.model_copy(update={"assignments": [a for a in old.assignments if a.work_id == "G-001"]})
    r = check_policy(only_gas, None, s)
    assert _severity(r, "protected_roads") == "fail"
    assert r.checks[0].detail == "G-001 would cut a protected road"
    s.works[2] = s.works[2].model_copy(update={"is_emergency": True})
    assert _severity(check_policy(only_gas, None, s), "protected_roads") == "ok"
