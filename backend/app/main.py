import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import ledger, store
from backend.app.config import get_settings
from backend.app.db import init_db, session
from backend.app.deps import build_wiring
from backend.app.routers import (
    approvals,
    city,
    copilot,
    evidence,
    files,
    health,
    insight,
    live,
    plans,
    reports,
    risk,
    works,
)
from backend.app.routers import ledger as ledger_router
from backend.app.runstore import open_run_store
from contracts.models import Scenario

# uvicorn shows only its own loggers; this shows the app's INFO lines (run store, stand-ins) and keeps httpx's per-request lines quiet
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


def load_scenario(app: FastAPI, seed: int) -> Scenario:
    """Generate a test case, store it and save its old-way plan P-OLD-<seed>."""
    scenario = app.state.wiring.pure_generate(seed)
    with session() as s:
        store.put_scenario(s, scenario)
    plans.save_old_way(app.state.wiring.deps, scenario)
    with session() as s:
        ledger.append(s, "system", "scenario.loaded", f"scenario:{seed}",
                      f"Loaded test case {seed}: {len(scenario.works)} works on {len(scenario.segments)} road segments",
                      {"seed": seed, "works": len(scenario.works), "segments": len(scenario.segments)})
    return scenario


def _is_stored(seed: int) -> bool:
    with session() as s:
        return store.get_scenario(s, seed) is not None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with contextlib.AsyncExitStack() as stack:
        await asyncio.to_thread(init_db)
        app.state.wiring = build_wiring()
        app.state.run_store = await open_run_store(stack, app.state.wiring)
        app.state.seed = get_settings().scenario_seed
        app.state.tasks = set()
        # shortcut: one API process; use a database lock if the API ever runs as several
        app.state.audit_lock = asyncio.Lock()
        if not await asyncio.to_thread(_is_stored, app.state.seed):
            await asyncio.to_thread(load_scenario, app, app.state.seed)
        yield
        for task in app.state.tasks:
            task.cancel()


app = FastAPI(title="MargaMitra API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_methods=["*"], allow_headers=["*"])
for r in (health, city, works, plans, risk, approvals, ledger_router, live, files, evidence, reports, insight, copilot):
    app.include_router(r.router)
