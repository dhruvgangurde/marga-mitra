from dataclasses import replace

from contracts.fakes import tiny_scenario
from contracts.models import NegotiationOutcome, PlanVariant, SolveConstraints
from evals.run import VARIANTS, eval_windows, load_parts, plan_variant, with_windows
from solver.baselines import naive_plan
from solver.metrics import compute_metrics


def by_id(plan) -> dict:
    return {a.work_id: a for a in plan.assignments}


async def five_plans(parts=None) -> dict:
    parts = parts or load_parts(use_real=False)
    scenario = tiny_scenario(1)
    naive = naive_plan(scenario)
    return {v: await plan_variant(v, scenario, parts, naive) for v in VARIANTS}


def stormy():
    s = tiny_scenario(1)
    return with_windows(s, eval_windows(s, load_parts(use_real=False)))


async def test_the_variants_and_the_old_way():
    plans = await five_plans()
    assert [plans[v].variant for v in VARIANTS] == [PlanVariant.naive, PlanVariant.solver_only, PlanVariant.agents,
                                                     PlanVariant.orchestrated, PlanVariant.orchestrated]
    assert plans["naive"].model_dump(exclude={"created_at"}) == \
        naive_plan(tiny_scenario(1)).model_dump(exclude={"created_at"})
    assert all(a.shared_group is None for a in plans["solver_only"].assignments)
    assert plans["full"].assignments == plans["risk"].assignments


async def test_empty_constraints_change_nothing():
    plans = await five_plans()
    assert plans["agents"].assignments == plans["solver_only"].assignments


async def test_an_agreed_trench_saves_money():
    async def share(scenario, plan, conflicts, run_id, emit):
        return NegotiationOutcome(run_id=run_id, rounds=1, messages=[], constraints=SolveConstraints(shared_groups=["G1"]),
                                  used_llm=False)

    plans = await five_plans(replace(load_parts(use_real=False), negotiate=share))
    a = by_id(plans["agents"])
    assert a["W-001"].shared_group == a["T-001"].shared_group == "G1"
    s = stormy()
    assert compute_metrics(plans["agents"], s).cost_inr < compute_metrics(plans["solver_only"], s).cost_inr


async def test_forecasts_keep_trenches_out_of_the_rain():
    plans = await five_plans()
    s = stormy()
    assert compute_metrics(plans["risk"], s).trench_hours_in_rain <= compute_metrics(plans["naive"], s).trench_hours_in_rain


async def test_the_run_ids_name_the_case_and_variant():
    seen: list[str] = []

    async def record(scenario, plan, conflicts, run_id, emit):
        seen.append(run_id)
        return NegotiationOutcome(run_id=run_id, rounds=0, messages=[], constraints=SolveConstraints(), used_llm=False)

    await five_plans(replace(load_parts(use_real=False), negotiate=record))
    assert seen == ["EVAL-1-agents", "EVAL-1-risk", "EVAL-1-risk"]
