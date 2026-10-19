from datetime import date

from contracts.fakes import tiny_scenario
from contracts.models import Mode, Plan, Scenario, SolveConstraints
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
