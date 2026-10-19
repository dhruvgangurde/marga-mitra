"""The demo story on test case 1. Skips until Track 4 merges data.scenario."""
import pytest

from contracts import rules
from contracts.models import Mode, Plan, RiskKind, RiskWindow, Scenario, SolveConstraints
from solver.baselines import naive_plan
from solver.solve import solve

MUNCHUR = ("W-104", "T-221", "G-310", "R-501")


def by_id(plan: Plan) -> dict:
    return {a.work_id: a for a in plan.assignments}


def days(a) -> set[int]:
    return set(range(a.start_day, a.end_day + 1))


def orchestrate(scenario: Scenario) -> Plan:
    group = next(g for g in scenario.parallel_groups if {"W-104", "T-221"} <= set(g.work_ids))
    return solve(scenario, SolveConstraints(shared_groups=[group.group_id], use_risk=True))


def test_old_way_digs_munchur_road_four_times():
    scenario_module = pytest.importorskip("data.scenario")
    scenario = scenario_module.generate_scenario(1)
    plan = naive_plan(scenario)
    works = {w.work_id: w for w in scenario.works}
    segs = {s for wid in MUNCHUR for s in works[wid].segment_ids}
    digs = rules.digs_per_segment(scenario, plan)
    assert max(digs.get(s, 0) for s in segs) == 4
    assert rules.clash_count(scenario, plan) == 9


def test_orchestrated_plan_shares_the_trench_and_resurfaces_last():
    scenario_module = pytest.importorskip("data.scenario")
    scenario = scenario_module.generate_scenario(1)
    plan = orchestrate(scenario)
    a = by_id(plan)
    w, t, g, r = (a[wid] for wid in MUNCHUR)
    assert w.shared_group is not None and w.shared_group == t.shared_group
    assert (w.start_day, w.end_day) == (t.start_day, t.end_day)
    assert g.start_day > w.end_day
    assert r.start_day > max(w.end_day, t.end_day, g.end_day)
    assert rules.clash_count(scenario, plan) == 0
    assert a["P-120"].mode == a["G-305"].mode == Mode.trenchless


def test_heavy_rain_moves_open_trenches_off_low_roads():
    scenario_module = pytest.importorskip("data.scenario")
    scenario = scenario_module.generate_scenario(1)
    low = [s.segment_id for s in scenario.segments if s.low_lying]
    rain = RiskWindow(window_id="OV-1", kind=RiskKind.rain, start_day=12, end_day=13, segment_ids=low, value=70,
                      source="override", label="Heavy rain, 14–15 Nov")
    scenario = scenario.model_copy(update={"risk_windows": [*scenario.risk_windows, rain]})
    plan = orchestrate(scenario)
    assert rules.rain_trench_hours(scenario, plan) == 0
    a = by_id(plan)
    for wid in ("D-412", "P-118", "W-118"):
        assert a[wid].mode != Mode.open_cut or not days(a[wid]) & {12, 13}, wid


def test_the_procession_keeps_its_route_free():
    scenario_module = pytest.importorskip("data.scenario")
    scenario = scenario_module.generate_scenario(1)
    event = next(win for win in scenario.risk_windows if win.kind == RiskKind.event)
    plan = orchestrate(scenario)
    works = {w.work_id: w for w in scenario.works}
    window = set(range(event.start_day, event.end_day + 1))
    for a in plan.assignments:
        if set(works[a.work_id].segment_ids) & set(event.segment_ids):
            assert not days(a) & window, a.work_id
