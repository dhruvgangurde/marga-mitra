import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app import ledger, store
from backend.app.db import session
from backend.app.schemas import Department, NoDigEntry, ScenarioLoaded
from contracts import costs
from contracts.models import Dept, LedgerEntry, WsEvent

router = APIRouter(tags=["city"])

DEPARTMENTS = [
    Department(id="water", name="Water", icon="drop", color_token="--dept-water"),
    Department(id="drainage", name="Drainage", icon="waves", color_token="--dept-drainage"),
    Department(id="gas", name="Gas", icon="flame", color_token="--dept-gas"),
    Department(id="power", name="Power", icon="lightning", color_token="--dept-power"),
    Department(id="telecom", name="Telecom", icon="wifi", color_token="--dept-telecom"),
    Department(id="roads", name="Roads", icon="road", color_token="--dept-roads"),
]
DEPT_NAMES = {d.id: d.name for d in DEPARTMENTS}


def _newest_entry() -> LedgerEntry:
    with session() as s:
        return ledger.latest(s, 1)[0]


@router.post("/scenario/load")
async def load(request: Request, seed: int = Query(1, ge=1)) -> ScenarioLoaded:
    from backend.app.main import load_scenario  # main imports this router, so import it at call time

    scenario = await asyncio.to_thread(load_scenario, request.app, seed)
    request.app.state.seed = seed
    # shortcut: the newest entry is the one load_scenario just wrote; fine for one API process
    entry = await asyncio.to_thread(_newest_entry)
    await request.app.state.wiring.deps.emit(
        WsEvent(type="ledger.appended", data=entry.model_dump(mode="json"), ts=datetime.now(UTC)))
    return ScenarioLoaded(seed=seed, start_date=scenario.start_date, works=len(scenario.works),
                          segments=len(scenario.segments))


def _bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    try:
        parts = tuple(float(p) for p in raw.split(","))
    except ValueError:
        parts = ()
    if len(parts) != 4:
        raise HTTPException(422, "bbox must be four numbers: minLon,minLat,maxLon,maxLat.")
    return parts


@router.get("/segments")
def segments(bbox: str | None = None) -> dict[str, Any]:
    box = _bbox(bbox)
    with session() as s:
        return store.segments_geojson(s, box)


def _demo_protected() -> dict[str, tuple[str, str]]:
    """Segment id -> (road label, why) for the demo's protected roads; empty without the data track's demo."""
    try:
        from data import demo
    except ModuleNotFoundError:
        return {}
    return {sid: (road, why) for road, (_until, why) in demo.PROTECTED_ROADS.items() for sid in demo.DEMO_ROADS[road]}


def _no_dig(seed: int) -> list[NoDigEntry]:
    with session() as s:
        scenario = store.get_scenario(s, seed)
        plan = store.active_plan(s, seed)
    entries: dict[str, NoDigEntry] = {}

    def keep(entry: NoDigEntry) -> None:  # one entry per segment, the later date wins
        old = entries.get(entry.segment_id)
        if old is None or entry.protected_until > old.protected_until:
            entries[entry.segment_id] = entry

    demo = _demo_protected()
    for seg in scenario.segments if scenario else []:
        if seg.protected_until:
            name, why = demo.get(seg.segment_id, (seg.name or "Unnamed road", "Resurfaced recently"))
            keep(NoDigEntry(segment_id=seg.segment_id, name=name, protected_until=seg.protected_until, why=why))
    works = {w.work_id: w for w in scenario.works} if scenario else {}
    after = costs.policy()["no_dig_days_after_restoration"]
    for a in plan.assignments if plan else []:
        w = works.get(a.work_id)
        if w is None or w.dept != Dept.roads or w.done:
            continue
        until = scenario.start_date + timedelta(days=a.end_day + after)
        for sid in w.segment_ids:
            keep(NoDigEntry(segment_id=sid, name=w.road_name, protected_until=until,
                            why=f"From the planned resurfacing {w.work_id}"))
    return sorted(entries.values(), key=lambda e: (e.name, e.segment_id))


@router.get("/no-dig")
def no_dig(request: Request) -> list[NoDigEntry]:
    return _no_dig(request.app.state.seed)


@router.get("/departments")
def departments() -> list[Department]:
    return DEPARTMENTS
