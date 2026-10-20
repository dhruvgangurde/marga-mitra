import asyncio
import re
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import text

from backend.app import storage, store
from backend.app.auditor import safe_audit
from backend.app.config import get_settings
from backend.app.db import session
from backend.app.ids import next_id, next_work_id
from backend.app.routers.evidence import add_photo, newest_pair, verify_work, work_or_404
from backend.app.routers.plans import start_background_run
from backend.app.schemas import ConfirmationIn
from contracts import costs
from contracts.models import CitizenReport, Dept, Mode, Work

router = APIRouter(tags=["residents"])

Category = Literal["water", "gas", "power", "cavein", "trench"]
# category -> department, work title, what the resident reported
EMERGENCY: dict[str, tuple[Dept, str, str]] = {
    "water": (Dept.water, "Burst water pipe", "a burst water pipe"),
    "gas": (Dept.gas, "Gas smell", "a gas smell"),
    "power": (Dept.power, "Cable cut or sparking", "a cut or sparking cable"),
    "cavein": (Dept.roads, "Road has caved in", "a road cave-in"),
    "trench": (Dept.roads, "Open trench left unsafe", "an unsafe open trench"),
}
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?\d{5}[\s-]?\d{5}(?!\d)")
MAX_ROAD_M = 1000


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


def _emergency_work(seed: int, category: str, lat: float, lon: float) -> Work:
    """The new emergency work on the nearest road; one at a time, so two reports never get the same id."""
    dept, title, _ = EMERGENCY[category]
    today = get_settings().today_day
    with session() as s:
        s.execute(text("SELECT pg_advisory_xact_lock(4244)"))
        scenario = store.get_scenario(s, seed)
        found = store.nearest_segment(s, [g.segment_id for g in scenario.segments], lat, lon)
        if found is None or found[1] > MAX_ROAD_M:
            raise HTTPException(422, "This place is too far from the roads on the city map.")
        seg = next(g for g in scenario.segments if g.segment_id == found[0])
        road = seg.name or next((w.road_name for w in scenario.works if seg.segment_id in w.segment_ids), "Unnamed road")
        length = round(seg.length_m, 1)
        work = Work(work_id=next_work_id(scenario, dept), dept=dept, title=title, road_name=road,
                    segment_ids=[seg.segment_id], length_m=length, requested_start=today, earliest_start=today,
                    latest_end=min(today + 1, scenario.horizon_days - 1),
                    modes=[costs.mode_option(dept, length, Mode.open_cut, 2, 1)], priority=5,
                    deposit_inr=costs.deposit_inr(dept, length, Mode.open_cut), is_emergency=True)
        store.add_work(s, seed, work)
    return work


def _save_emergency(seed: int, category: str, work: Work, lat: float, lon: float, note: str,
                    photo_url: str | None) -> CitizenReport:
    with session() as s:
        report = CitizenReport(report_id=next_id(s, "CR"), kind="emergency", category=category, work_id=work.work_id,
                               lat=lat, lon=lon, note=note, photo_url=photo_url, created_at=store.db_now(s))
        store.add_report(s, seed, report)
    return report


@router.post("/reports/emergency", status_code=201)
async def emergency(
    request: Request,
    category: Annotated[Category, Form()],
    lat: Annotated[float, Form(ge=-90, le=90)],
    lon: Annotated[float, Form(ge=-180, le=180)],
    note: Annotated[str, Form(max_length=280)] = "",
    photo: Annotated[UploadFile | None, File()] = None,
) -> CitizenReport:
    """A resident's emergency: a new emergency work, allowed at once, then a re-plan. Never a name or a phone number."""
    app, seed = request.app, request.app.state.seed
    data = await photo.read(storage.MAX_PHOTO_BYTES + 1) if photo else None
    try:
        ext = storage.check_photo(data) if data is not None else None
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    note = PHONE.sub("[number removed]", note)
    work = await asyncio.to_thread(_emergency_work, seed, category, lat, lon)
    photo_url = None
    if data is not None:
        photo_url = (await add_photo(app, seed, work, "citizen", data, ext, lat, lon, None)).file_url
    report = await asyncio.to_thread(_save_emergency, seed, category, work, lat, lon, note, photo_url)
    phrase, entity = EMERGENCY[category][2], f"work:{work.work_id}"
    deps = app.state.wiring.deps
    await deps.ledger_append("resident", "emergency.reported", entity, f"Reported {phrase} on {work.road_name}",
                             report.model_dump(mode="json"))
    await deps.ledger_append("rules", "emergency.allowed", entity,
                             f"Emergency dig allowed at once: {phrase.split(' ', 1)[1]}", work.model_dump(mode="json"))
    await start_background_run(app, seed, "emergency")
    await safe_audit(app)
    return report
