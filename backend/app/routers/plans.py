import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI, HTTPException, Request

from backend.app import store
from backend.app.auditor import safe_audit
from backend.app.db import session
from backend.app.deps import in_session, with_windows
from backend.app.ids import next_id
from backend.app.schemas import WhatIfIn, WhatIfResult
from contracts.interfaces import Deps
from contracts.models import (
    Metrics,
    NegotiationMessage,
    Plan,
    PlanStatus,
    PlanVariant,
    RunResult,
    Scenario,
    SolveConstraints,
    WorkChange,
    WsEvent,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["plans"])


def _saved_draft(plan: Plan, plan_id: str) -> Plan:
    plan = plan.model_copy(update={"plan_id": plan_id, "status": PlanStatus.draft})
    in_session(store.save_plan, plan)
    return plan


def save_old_way(deps: Deps, scenario: Scenario) -> Plan:
    """The old way of a test case: first come, first dug, saved as P-OLD-<seed>."""
    return _saved_draft(deps.naive_plan(with_windows(deps, scenario)), f"P-OLD-{scenario.seed}")


def current_scenario(app: FastAPI) -> Scenario:
    """The stored test case with today's risk windows, as plans, rules and metrics see it."""
    deps = app.state.wiring.deps
    return with_windows(deps, deps.generate_scenario(app.state.seed))


def _deps_and_scenario(request: Request, seed: int | None = None) -> tuple[Deps, Scenario]:
    deps = request.app.state.wiring.deps
    return deps, with_windows(deps, deps.generate_scenario(seed or request.app.state.seed))


def _plan_or_404(plan_id: str) -> Plan:
    plan = in_session(store.get_plan, plan_id)
    if plan is None:
        raise HTTPException(404, f"There is no plan {plan_id}.")
    return plan


async def emit_plan_updated(deps: Deps, plan_id: str | None, metrics: Metrics | None) -> None:
    plan = await deps.load_plan(plan_id) if plan_id else None
    if plan is None:
        return
    data = {"plan_id": plan.plan_id, "status": plan.status.value, "variant": plan.variant.value,
            "metrics": metrics.model_dump(mode="json") if metrics else None}
    await deps.emit(WsEvent(type="plan.updated", data=data, ts=datetime.now(UTC)))


def _new_run(seed: int, reason: str) -> tuple[RunResult, str | None]:
    with session() as s:
        result = store.create_run(s, next_id(s, "RUN"), seed, reason)
        base = store.active_plan(s, seed)
    return result, base.plan_id if base else None


async def _run(app: FastAPI, run_id: str, seed: int, reason: str, base_plan_id: str | None) -> None:
    wiring = app.state.wiring
    try:
        result = await wiring.start_run(wiring.deps, run_id, seed, reason, base_plan_id)
        await asyncio.to_thread(in_session, store.update_run, result)
        await emit_plan_updated(wiring.deps, result.plan_id, result.metrics)
    except Exception:  # any failure in another track's workflow must still leave the run marked failed
        logger.exception("Run %s failed", run_id)
        failed = RunResult(run_id=run_id, status="failed", note="The plan could not be made.")
        await asyncio.to_thread(in_session, store.update_run, failed)
    await safe_audit(app)


async def start_background_run(app: FastAPI, seed: int, reason: str) -> RunResult:
    result, base_plan_id = await asyncio.to_thread(_new_run, seed, reason)
    task = asyncio.create_task(_run(app, result.run_id, seed, reason, base_plan_id))
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)
    return result


@router.post("/plan/naive")
def naive(request: Request) -> Plan:
    deps, scenario = _deps_and_scenario(request)
    return save_old_way(deps, scenario)


@router.post("/plan/solver-only")
def solver_only(request: Request) -> Plan:
    deps, scenario = _deps_and_scenario(request)
    plan = deps.solve(scenario, SolveConstraints(use_risk=False, use_groups=False), PlanVariant.solver_only)
    return _saved_draft(plan, f"P-SOLO-{scenario.seed}")


@router.post("/plan/orchestrate")
async def orchestrate(request: Request) -> RunResult:
    return await start_background_run(request.app, request.app.state.seed, "orchestrate")


@router.get("/plans")
def list_plans(request: Request) -> list[Plan]:
    with session() as s:
        return store.list_plans(s, request.app.state.seed)


@router.get("/plan/{plan_id}")
def get_plan(plan_id: str) -> Plan:
    return _plan_or_404(plan_id)


@router.get("/plan/{plan_id}/metrics")
def metrics(request: Request, plan_id: str) -> Metrics:
    plan = _plan_or_404(plan_id)
    deps, scenario = _deps_and_scenario(request, plan.seed)
    return deps.compute_metrics(plan, scenario)


@router.get("/plan/{plan_id}/diff")
def diff(request: Request, plan_id: str, against: str = "naive") -> list[WorkChange]:
    plan = _plan_or_404(plan_id)
    deps, scenario = _deps_and_scenario(request, plan.seed)
    if against == "naive":
        old = in_session(store.get_plan, f"P-OLD-{plan.seed}") or save_old_way(deps, scenario)
    else:
        old = _plan_or_404(against)
    return deps.plan_diff(old, plan, scenario)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> RunResult:
    result = in_session(store.get_run, run_id)
    if result is None:
        raise HTTPException(404, f"There is no run {run_id}.")
    return result


@router.get("/negotiation")
def negotiation(request: Request, run_id: str | None = None) -> list[NegotiationMessage]:
    with session() as s:
        run_id = run_id or store.newest_run_id(s, request.app.state.seed)
        return store.list_messages(s, run_id) if run_id else []


def _whatif_constraints(active: Plan, scenario: Scenario, work_id: str, delay_days: int) -> SolveConstraints:
    works = {w.work_id: w for w in scenario.works}
    starts = {a.work_id: a.start_day for a in active.assignments}
    group = next(a.shared_group for a in active.assignments if a.work_id == work_id)
    moving = {a.work_id for a in active.assignments if a.work_id == work_id or (group and a.shared_group == group)}
    segments = {s for w in moving for s in works[w].segment_ids}
    neighbours = {w for w in starts if w not in moving and w in works and set(works[w].segment_ids) & segments}
    # Neighbours may only move later, so the answer shows the knock-on and nothing else changes.
    min_start = {w: starts[w] + (delay_days if w == work_id else 0) for w in sorted(moving | neighbours)}
    return SolveConstraints(min_start=min_start,
                            pinned_start={w: s for w, s in sorted(starts.items()) if w not in min_start},
                            shared_groups=sorted({a.shared_group for a in active.assignments if a.shared_group}))


@router.post("/plan/whatif")
def whatif(request: Request, body: WhatIfIn) -> WhatIfResult:
    """The plan if one work started later. Nothing is saved, recorded or sent live."""
    deps, scenario = request.app.state.wiring.deps, current_scenario(request.app)
    work = next((w for w in scenario.works if w.work_id == body.work_id), None)
    if work is None:
        raise HTTPException(404, "Unknown work.")
    if work.is_emergency:
        raise HTTPException(422, "An emergency dig cannot be moved.")
    active = in_session(store.active_plan, request.app.state.seed)
    if active is None or all(a.work_id != work.work_id for a in active.assignments):
        raise HTTPException(422, f"{work.work_id} is not in the current plan.")
    constraints = _whatif_constraints(active, scenario, work.work_id, body.delay_days)
    plan = deps.solve(scenario, constraints, PlanVariant.whatif).model_copy(update={
        "plan_id": "P-WHATIF", "variant": PlanVariant.whatif, "status": PlanStatus.draft, "base_plan_id": active.plan_id})
    return WhatIfResult(plan=plan, diff=deps.plan_diff(active, plan, scenario), metrics=deps.compute_metrics(plan, scenario))
