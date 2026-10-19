import pytest

from agents import conflicts, coordinator
from agents.workflow import resume_run, start_run
from contracts import rules
from contracts.fakes import MemoryStore, fake_deps, fake_solve, tiny_scenario
from contracts.models import PlanVariant


class Spy:
    """Wraps a scheduler and records every constraints argument it was given."""

    def __init__(self, inner):
        self.inner = inner
        self.constraints = []

    def __call__(self, scenario, constraints, variant=PlanVariant.orchestrated):
        self.constraints.append(constraints)
        return self.inner(scenario, constraints, variant)


def build(scenario_fn=tiny_scenario, affected=("W-001",)):
    store = MemoryStore()
    deps = fake_deps(store)
    spy = Spy(fake_solve)
    deps.negotiate = coordinator.negotiate
    deps.detect_conflicts = conflicts.detect_conflicts
    deps.solve = spy
    deps.generate_scenario = scenario_fn
    deps.affected_works = lambda scenario, plan, windows: list(affected)
    return store, deps, spy


def emergency_on(work_id):
    def scenario(seed=0):
        s = tiny_scenario(seed)
        return s.model_copy(update={"works": [w.model_copy(update={"is_emergency": True}) if w.work_id == work_id else w
                                              for w in s.works]})

    return scenario


def with_second_emergency(seed=0):
    s = tiny_scenario(seed)
    water = next(w for w in s.works if w.work_id == "W-001")
    return s.model_copy(update={"works": [*s.works, water.model_copy(update={"work_id": "W-002", "is_emergency": True})]})


def touched(c):
    return set(c.pinned_start) | set(c.min_start) | set(c.forbidden_days)


async def approved_first_run(deps):
    await start_run(deps, "RUN-0001", 1)
    await resume_run(deps, "RUN-0001", "approve", "ward_engineer")


async def test_a_rain_replan_moves_only_what_the_forecast_touches():
    store, deps, spy = build()
    await approved_first_run(deps)
    result = await start_run(deps, "RUN-0002", 1, "rain", base_plan_id="P-0001")
    assert result.status == "waiting_approval"
    last = spy.constraints[-1]
    assert last.pinned_start == {"T-001": 10, "G-001": 9, "R-001": 9}
    assert last.min_start == {}
    assert last.shared_groups == []
    first = next(e.data for e in store.events if e.type == "negotiation.message" and e.data["run_id"] == "RUN-0002")
    assert first["type"] == "NOTICE"
    assert first["work_ids"] == ["W-001", "T-001", "R-001"]
    assert store.plans["P-0002"].base_plan_id == "P-0001"


async def test_an_emergency_work_is_left_to_the_scheduler():
    _, deps, spy = build(emergency_on("W-001"))
    await start_run(deps, "RUN-0001", 1)
    last = spy.constraints[-1]
    assert "W-001" not in touched(last)
    assert last.shared_groups == []


async def test_an_emergency_replan_reaches_the_works_on_its_road():
    _, deps, spy = build(affected=())
    await approved_first_run(deps)
    deps.generate_scenario = with_second_emergency
    await start_run(deps, "RUN-0002", 1, "emergency", base_plan_id="P-0001")
    last = spy.constraints[-1]
    assert last.pinned_start == {"G-001": 9}
    assert last.shared_groups == ["G1"]
    assert "W-002" not in touched(last)


async def test_the_real_scheduler_makes_one_trench_and_no_clashes():
    pytest.importorskip("solver.solve")
    pytest.importorskip("solver.metrics")
    pytest.importorskip("solver.diff")
    from solver.baselines import naive_plan
    from solver.diff import plan_diff
    from solver.metrics import compute_metrics
    from solver.solve import solve

    store, deps, _ = build()
    deps.naive_plan, deps.solve, deps.compute_metrics, deps.plan_diff = naive_plan, solve, compute_metrics, plan_diff
    result = await start_run(deps, "RUN-0001", 1)
    assert result.status == "waiting_approval"
    s = tiny_scenario()
    plan = store.plans["P-0001"]
    by_id = {a.work_id: a for a in plan.assignments}
    assert by_id["W-001"].shared_group == by_id["T-001"].shared_group == "G1"
    assert (by_id["W-001"].start_day, by_id["W-001"].end_day) == (by_id["T-001"].start_day, by_id["T-001"].end_day)
    assert rules.clash_count(s, plan) == 0
    assert rules.rain_trench_hours(s, plan) == 0.0
    decision = next(e.data for e in store.events if e.type == "negotiation.message" and e.data["type"] == "DECISION")
    assert decision["body"] == ("The new plan: digs per road 2.7 → 2.0, lane-closure hours 450 → 360, clashes 4 → 0. "
                                "Trench-hours in rain: 48 → 0.")
