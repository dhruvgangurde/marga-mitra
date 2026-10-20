import asyncio

from fastapi import APIRouter, HTTPException, Request

from backend.app import store
from backend.app.config import get_settings
from backend.app.db import session
from backend.app.routers.city import DEPT_NAMES
from contracts.models import Assignment, Work, WorkStatus, WorkView

router = APIRouter(tags=["works"])


def work_status(work: Work, a: Assignment | None, today: int) -> WorkStatus:
    """First match wins. Verified and held arrive with the photo checks in Phase 2."""
    if work.is_emergency:
        return WorkStatus.emergency
    if work.done:
        return WorkStatus.done
    if a is None:
        return WorkStatus.planned
    if a.start_day <= today <= a.end_day:
        return WorkStatus.digging
    if a.shared_group:
        return WorkStatus.shared
    if a.start_day != work.requested_start or a.mode != work.modes[0].mode:
        return WorkStatus.moved
    return WorkStatus.planned


def _views(seed: int, plan_id: str | None) -> list[WorkView]:
    with session() as s:
        scenario = store.get_scenario(s, seed)
        plan = store.get_plan(s, plan_id) if plan_id else store.active_plan(s, seed)
    if plan_id and plan is None:
        raise HTTPException(404, f"There is no plan {plan_id}.")
    by_work = {a.work_id: a for a in plan.assignments} if plan else {}
    today = get_settings().today_day
    return [WorkView(work=w, assignment=by_work.get(w.work_id), status=work_status(w, by_work.get(w.work_id), today))
            for w in scenario.works]


@router.get("/works")
def list_works(request: Request, plan_id: str | None = None) -> list[WorkView]:
    return _views(request.app.state.seed, plan_id)


@router.get("/works/{work_id}")
def get_work(request: Request, work_id: str) -> WorkView:
    view = next((v for v in _views(request.app.state.seed, None) if v.work.work_id == work_id), None)
    if view is None:
        raise HTTPException(404, f"There is no work {work_id} in this test case.")
    return view


def _add(seed: int, work: Work) -> None:
    with session() as s:
        store.add_work(s, seed, work)


@router.post("/works", status_code=201)
async def add_work(request: Request, work: Work) -> Work:
    try:
        await asyncio.to_thread(_add, request.app.state.seed, work)
    except ValueError as e:
        if str(e) == "exists":
            raise HTTPException(409, f"Work {work.work_id} already exists.") from e
        raise HTTPException(422, f"Work {work.work_id} is on a road this test case does not have.") from e
    await request.app.state.wiring.deps.ledger_append(
        work.dept.value, "work.added", f"work:{work.work_id}",
        f"{DEPT_NAMES[work.dept.value]} added {work.work_id}: {work.title}, {work.road_name}", work.model_dump(mode="json"))
    return work
