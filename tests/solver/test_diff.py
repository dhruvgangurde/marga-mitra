from contracts.fakes import tiny_scenario
from solver.baselines import naive_plan
from solver.diff import plan_diff
from tests.solver.test_metrics import hand_plan


def test_diff_against_the_hand_made_plan():
    s = tiny_scenario()
    changes = plan_diff(naive_plan(s), hand_plan(s), s)
    assert [c.work_id for c in changes] == ["W-001", "T-001", "G-001", "R-001"]
    assert [c.cost_delta_inr for c in changes] == [-336000, -336000, 8000, 16000]
    assert [c.title for c in changes] == ["Water main, Test Road · W-001", "Fibre duct, Test Road · T-001",
                                          "Gas line, Test Road · G-001", "Resurfacing, Test Road · R-001"]
    w, t = changes[0], changes[1]
    assert (w.from_start, w.from_end, w.to_start, w.to_end, w.shared_group) == (8, 12, 8, 12, "G1")
    assert (t.from_start, t.from_end, t.to_start, t.to_end) == (10, 12, 8, 12)


def test_same_plan_has_no_changes():
    s = tiny_scenario()
    assert plan_diff(naive_plan(s), naive_plan(s), s) == []


def test_work_missing_from_old_plan():
    s = tiny_scenario()
    old = naive_plan(s)
    old = old.model_copy(update={"assignments": [a for a in old.assignments if a.work_id != "G-001"]})
    g = next(c for c in plan_diff(old, hand_plan(s), s) if c.work_id == "G-001")
    assert (g.from_start, g.from_end, g.mode_from, g.cost_delta_inr) == (None, None, None, 8000)
