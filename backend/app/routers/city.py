import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app import ledger, store
from backend.app.db import session
from backend.app.schemas import Department, ScenarioLoaded
from contracts.models import LedgerEntry, WsEvent

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


@router.get("/departments")
def departments() -> list[Department]:
    return DEPARTMENTS
