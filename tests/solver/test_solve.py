from datetime import date

from contracts import rules
from contracts.fakes import tiny_scenario
from contracts.models import Mode, Plan, RiskKind, RiskWindow, Scenario, SolveConstraints
from solver.metrics import compute_metrics
from solver.solve import solve

BANNED = ("CP-SAT", "solver", "objective", "LLM")


def run(scenario: Scenario, constraints: SolveConstraints) -> Plan:
    """Solve and check that every line shown to people is in plain words."""
    plan = solve(scenario, constraints)
    for text in [a.reason for a in plan.assignments] + plan.notes:
        assert not any(b.lower() in text.lower() for b in BANNED), text
    return plan


def by_id(plan: Plan) -> dict:
    return {a.work_id: a for a in plan.assignments}


def test_pins_min_start_and_forbidden_days():
    c = SolveConstraints(pinned_start={"G-001": 15}, min_start={"T-001": 14}, forbidden_days={"W-001": [5, 6, 7]})
    a = by_id(run(tiny_scenario(), c))
    assert a["G-001"].start_day == 15
    assert a["T-001"].start_day >= 14
    assert not set(range(a["W-001"].start_day, a["W-001"].end_day + 1)) & {5, 6, 7}


def test_a_work_that_cannot_fit_is_unplanned():
    s = tiny_scenario()
    s.works[0] = s.works[0].model_copy(update={"latest_end": 3})
    plan = run(s, SolveConstraints())
    assert plan.unplanned == ["W-001"]
    assert sum("W-001" in n for n in plan.notes) == 1


def test_protected_road_forces_trenchless():
    s = tiny_scenario()
    s.segments[2] = s.segments[2].model_copy(update={"protected_until": date(2029, 1, 1)})
    plan = run(s, SolveConstraints(use_risk=False))
    g = by_id(plan)["G-001"]
    assert g.mode == Mode.trenchless
    assert g.reason == "Trenchless: Test Road is a protected road."
    assert "R-001" in plan.unplanned


def test_same_input_same_plan():
    c = SolveConstraints(shared_groups=["G1"])
    p1, p2 = run(tiny_scenario(), c), run(tiny_scenario(), c)
    assert p1.assignments == p2.assignments
    assert p1.unplanned == p2.unplanned
    assert p1.objective == p2.objective


def test_no_clashes_without_risk():
    s = tiny_scenario()
    plan = run(s, SolveConstraints(use_risk=False))
    assert rules.clash_count(s, plan) == 0
    assert rules.find_clashes(s, plan, include_risk=False) == []


def test_resurfacing_comes_after_every_utility_cut():
    s = tiny_scenario()
    a = by_id(run(s, SolveConstraints(use_risk=False)))
    r = a["R-001"]
    works = {w.work_id: w for w in s.works}
    for wid in ("W-001", "T-001", "G-001"):
        if a[wid].mode == Mode.open_cut and set(works[wid].segment_ids) & set(works["R-001"].segment_ids):
            assert r.start_day > a[wid].end_day


def test_shared_trench():
    s = tiny_scenario()
    plan = run(s, SolveConstraints(shared_groups=["G1"], use_risk=False))
    a = by_id(plan)
    w, t = a["W-001"], a["T-001"]
    assert w.mode == t.mode == Mode.open_cut
    assert w.shared_group == t.shared_group == "G1"
    assert (w.start_day, w.end_day) == (t.start_day, t.end_day)
    assert w.end_day - w.start_day + 1 == 5
    assert rules.digs_per_segment(s, plan)["S-0001"] == 2
    assert t.reason == "Shares one trench with Water W-001."
    assert w.reason == "Shares one trench with Telecom T-001."
    apart = run(s, SolveConstraints(shared_groups=["G1"], use_risk=False, use_groups=False))
    assert compute_metrics(plan, s).cost_inr < compute_metrics(apart, s).cost_inr


def test_groups_off_or_unknown_share_nothing():
    for c in (SolveConstraints(shared_groups=["G1"], use_groups=False), SolveConstraints(shared_groups=["G9"])):
        assert all(a.shared_group is None for a in run(tiny_scenario(), c).assignments)


def test_a_trench_that_cannot_fit_is_planned_one_by_one():
    plan = run(tiny_scenario(), SolveConstraints(shared_groups=["G1"], forbidden_days={"T-001": list(range(28))[::4]}))
    assert all(a.shared_group is None for a in plan.assignments)
    assert any("Shared trench G1" in n for n in plan.notes)


def test_rain_moves_open_trenches_only_with_risk_on():
    s = tiny_scenario()
    off = run(s, SolveConstraints(min_start={"W-001": 8}, use_risk=False))
    assert rules.rain_trench_hours(s, off) == 48.0
    on = run(s, SolveConstraints(min_start={"W-001": 8}, use_risk=True))
    assert rules.rain_trench_hours(s, on) == 0.0
    assert by_id(on)["W-001"].reason == "Moved after the rain: the road is low-lying."


def with_event() -> Scenario:
    s = tiny_scenario()
    s.risk_windows.append(RiskWindow(window_id="EV-1", kind=RiskKind.event, start_day=9, end_day=10,
                                     segment_ids=["S-0003"], value=0, source="event", label="Market, 11–12 Nov"))
    return s


def test_event_keeps_its_road_free():
    a = by_id(run(with_event(), SolveConstraints()))
    for wid in ("G-001", "R-001"):
        assert not set(range(a[wid].start_day, a[wid].end_day + 1)) & {9, 10}


def test_event_is_ignored_with_risk_off():
    c = SolveConstraints(use_risk=False)
    assert run(with_event(), c).assignments == run(tiny_scenario(), c).assignments
