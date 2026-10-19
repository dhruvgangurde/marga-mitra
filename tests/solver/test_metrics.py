from contracts.fakes import tiny_scenario
from contracts.models import Mode, Plan, PlanVariant, Scenario
from solver.baselines import naive_plan
from solver.metrics import compute_metrics


def hand_plan(scenario: Scenario) -> Plan:
    """W-001 and T-001 in one trench on days 8-12, then gas, then resurfacing."""
    days = {"W-001": (8, 12, "G1"), "T-001": (8, 12, "G1"), "G-001": (13, 16, None), "R-001": (17, 19, None)}
    plan = naive_plan(scenario)
    assignments = [a.model_copy(update={"start_day": days[a.work_id][0], "end_day": days[a.work_id][1],
                                        "shared_group": days[a.work_id][2]}) for a in plan.assignments]
    return plan.model_copy(update={"plan_id": "P-0-hand", "assignments": assignments})


def metric_values(plan: Plan, scenario: Scenario) -> tuple:
    m = compute_metrics(plan, scenario)
    return (m.excavations, m.digs_per_road, m.lane_closure_hours, m.trench_hours_in_rain, m.clashes, m.days_late,
            m.cost_inr, m.dust_score)


def test_naive_plan_follows_the_requests():
    plan = naive_plan(tiny_scenario())
    assert plan.plan_id == "P-0-naive"
    assert plan.variant == PlanVariant.naive
    assert [(a.work_id, a.start_day, a.end_day) for a in plan.assignments] == [
        ("W-001", 8, 12), ("T-001", 10, 12), ("G-001", 9, 12), ("R-001", 9, 11)]
    assert all(a.mode == Mode.open_cut for a in plan.assignments)
    assert all(a.reason == "As the department asked." for a in plan.assignments)


def test_naive_metrics():
    s = tiny_scenario()
    assert metric_values(naive_plan(s), s) == (4, 2.7, 450.0, 48.0, 4, 0.0, 4988000, 9.0)


def test_hand_made_metrics():
    s = tiny_scenario()
    assert metric_values(hand_plan(s), s) == (3, 2.0, 360.0, 48.0, 0, 3.0, 4340000, 10.2)


def test_done_works_count_nowhere():
    s = tiny_scenario()
    s.works[3] = s.works[3].model_copy(update={"done": True})
    plan = naive_plan(s)
    assert len(plan.assignments) == 3
    assert metric_values(plan, s) == (3, 1.7, 360.0, 48.0, 1, 0.0, 3800000, 7.2)
