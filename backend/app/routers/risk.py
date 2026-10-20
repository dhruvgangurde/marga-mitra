import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from backend.app import store
from backend.app.db import session
from backend.app.deps import day_range
from backend.app.ids import next_id
from backend.app.routers.plans import start_background_run
from backend.app.schemas import EventIn, ForecastOverride
from contracts.interfaces import Deps
from contracts.models import RiskKind, RiskWindow, RunResult, WsEvent

router = APIRouter(tags=["risk"])


def _store_window(seed: int, prefix: str, make: Callable[[str], RiskWindow]) -> RiskWindow:
    with session() as s:
        window = make(next_id(s, prefix))
        store.add_window(s, seed, window)
    return window


async def _windows_changed(deps: Deps, seed: int) -> None:
    windows = await asyncio.to_thread(lambda: deps.compute_risk_windows(deps.generate_scenario(seed)))
    await deps.emit(WsEvent(type="risk.windows_changed", data={"windows": [w.model_dump(mode="json") for w in windows]},
                            ts=datetime.now(UTC)))


@router.get("/risk/windows")
def windows(request: Request) -> list[RiskWindow]:
    deps = request.app.state.wiring.deps
    return deps.compute_risk_windows(deps.generate_scenario(request.app.state.seed))


@router.post("/risk/forecast-override")
async def forecast_override(request: Request, body: ForecastOverride) -> RunResult:
    deps, seed = request.app.state.wiring.deps, request.app.state.seed
    scenario = await asyncio.to_thread(deps.generate_scenario, seed)
    word = "Heavy rain" if body.kind == "rain" else "Poor air"
    days = day_range(scenario.start_date, body.start_day, body.end_day)
    # segment_ids stay empty: the risk track fills in the default roads for an override
    window = await asyncio.to_thread(_store_window, seed, "OV", lambda wid: RiskWindow(
        window_id=wid, kind=RiskKind(body.kind), start_day=body.start_day, end_day=body.end_day, segment_ids=[],
        value=body.value, source="override", label=body.label or f"{word}, {days}"))
    await deps.ledger_append("forecast", "forecast.override", f"risk:{window.window_id}",
                             f"{word} {days} (simulated for the demo)", window.model_dump(mode="json"))
    await _windows_changed(deps, seed)
    return await start_background_run(request.app, seed, body.kind)


@router.post("/events")
async def add_event(request: Request, body: EventIn) -> RiskWindow:
    deps, seed = request.app.state.wiring.deps, request.app.state.seed
    scenario = await asyncio.to_thread(deps.generate_scenario, seed)
    unknown = set(body.segment_ids) - {g.segment_id for g in scenario.segments}
    if unknown:
        raise HTTPException(422, f"This test case has no road segment {', '.join(sorted(unknown))}.")
    window = await asyncio.to_thread(_store_window, seed, "EV", lambda wid: RiskWindow(
        window_id=wid, kind=RiskKind.event, start_day=body.start_day, end_day=body.end_day,
        segment_ids=body.segment_ids, value=0, source="event", label=body.label))
    await deps.ledger_append("system", "event.added", f"risk:{window.window_id}", f"Event added: {body.label}",
                             window.model_dump(mode="json"))
    await _windows_changed(deps, seed)
    return window
