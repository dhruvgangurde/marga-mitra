import asyncio

from fastapi import APIRouter, Request

from backend.app import store
from backend.app.db import session
from backend.app.ids import next_id
from backend.app.routers.evidence import newest_pair, verify_work, work_or_404
from backend.app.schemas import ConfirmationIn
from contracts.models import CitizenReport

router = APIRouter(tags=["residents"])


def _save(seed: int, body: ConfirmationIn) -> CitizenReport:
    with session() as s:
        report = CitizenReport(report_id=next_id(s, "CR"), kind="confirmation", work_id=body.work_id,
                               answer=body.answer, problems=body.problems, lat=body.lat, lon=body.lon,
                               created_at=store.db_now(s))
        store.add_report(s, seed, report)
    return report


def _summary(body: ConfirmationIn) -> str:
    if body.answer == "yes":
        return f"A resident confirmed the road is restored at {body.work_id}"
    problems = f": {', '.join(body.problems).lower()}" if body.problems else ""
    return f"A resident says the road at {body.work_id} is not restored yet{problems}"


@router.post("/reports/confirmation", status_code=201)
async def confirm(request: Request, body: ConfirmationIn) -> CitizenReport:
    seed = request.app.state.seed
    await asyncio.to_thread(work_or_404, seed, body.work_id)
    report = await asyncio.to_thread(_save, seed, body)
    action = "resident.confirmed" if body.answer == "yes" else "resident.not_yet"
    await request.app.state.wiring.deps.ledger_append("resident", action, f"work:{body.work_id}", _summary(body),
                                                      report.model_dump(mode="json"))
    if await asyncio.to_thread(newest_pair, seed, body.work_id):
        await verify_work(request.app, seed, body.work_id)
    return report
