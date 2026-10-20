import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request

from backend.app import store
from backend.app.db import session
from backend.app.deps import day_range, in_session
from backend.app.routers.plans import emit_plan_updated
from backend.app.schemas import ApprovalDecision
from contracts.interfaces import Deps
from contracts.models import Approval, PlanStatus, RunResult, WsEvent

logger = logging.getLogger(__name__)
router = APIRouter(tags=["approvals"])


@router.get("/approvals")
def list_approvals(status: Literal["pending", "approved", "rejected"] | None = None) -> list[Approval]:
    return in_session(store.list_approvals, status)


def _decide(approval_id: str, status: str, by: str, reason: str | None) -> Approval:
    with session() as s:
        current = store.get_approval(s, approval_id, lock=True)
        if current is None:
            raise HTTPException(404, f"There is no approval {approval_id}.")
        if current.status != "pending":
            raise HTTPException(409, f"Approval {approval_id} was already {current.status}.")
        return store.decide_approval(s, approval_id, status, by, reason)


async def _apply_without_run(deps: Deps, approval: Approval, status: PlanStatus, body: ApprovalDecision) -> RunResult:
    """What the run's apply step does, for a run that can no longer resume (e.g. kept in memory before a restart)."""
    plan = await deps.load_plan(approval.plan_id)
    if plan and plan.status != status:
        await deps.save_plan(plan.model_copy(update={"status": status}))
        scenario = await asyncio.to_thread(deps.generate_scenario, plan.seed)
        days = day_range(scenario.start_date, 0, scenario.horizon_days - 1)
        ids = {"run_id": approval.run_id, "approval_id": approval.approval_id}
        if status == PlanStatus.approved:
            await deps.ledger_append(body.by, "plan.approved", f"plan:{plan.plan_id}", f"Approved the plan for {days}", ids)
        else:
            await deps.ledger_append(body.by, "plan.rejected", f"plan:{plan.plan_id}",
                                     f"Rejected the plan for {days}: {body.reason}", {**ids, "reason": body.reason})
    run = await asyncio.to_thread(in_session, store.get_run, approval.run_id)
    base = run or RunResult(run_id=approval.run_id, status=status.value, plan_id=approval.plan_id)
    return base.model_copy(update={"status": status.value, "approval_id": approval.approval_id,
                                   "note": "Saved without the planning run, which had stopped."})


@router.post("/approvals/{approval_id}")
async def decide(request: Request, approval_id: str, body: ApprovalDecision) -> RunResult:
    if body.decision == "reject" and not (body.reason or "").strip():
        raise HTTPException(422, "Say why the plan is rejected.")
    wiring = request.app.state.wiring
    status = PlanStatus.approved if body.decision == "approve" else PlanStatus.rejected
    approval = await asyncio.to_thread(_decide, approval_id, status.value, body.by, body.reason)
    try:
        result = await wiring.resume_run(wiring.deps, approval.run_id, body.decision, body.by, body.reason)
    except Exception:  # the person's decision is saved even when the workflow cannot pick the run up again
        logger.exception("Run %s could not resume after approval %s", approval.run_id, approval_id)
        result = await _apply_without_run(wiring.deps, approval, status, body)
    await asyncio.to_thread(in_session, store.update_run, result)
    plan = await wiring.deps.load_plan(approval.plan_id)
    if plan and plan.status != status:  # the stand-in workflow does not save the decided plan
        await wiring.deps.save_plan(plan.model_copy(update={"status": status}))
    await wiring.deps.emit(WsEvent(type="approval.decided", data=approval.model_dump(mode="json"), ts=datetime.now(UTC)))
    await emit_plan_updated(wiring.deps, approval.plan_id, result.metrics)
    return result
