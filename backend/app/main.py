import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import ledger, store
from backend.app.config import get_settings
from backend.app.db import init_db, session
from backend.app.deps import build_wiring, with_windows
from backend.app.routers import city, health, plans, works
from backend.app.routers import ledger as ledger_router
from contracts.models import PlanStatus, Scenario


def load_scenario(app: FastAPI, seed: int) -> Scenario:
    """Generate a test case, store it and save its old-way plan P-OLD-<seed>."""
    deps = app.state.wiring.deps
    scenario = app.state.wiring.pure_generate(seed)
    with session() as s:
        store.put_scenario(s, scenario)
    old = deps.naive_plan(with_windows(deps, scenario)).model_copy(
        update={"plan_id": f"P-OLD-{seed}", "status": PlanStatus.draft})
    with session() as s:
        store.save_plan(s, old)
        ledger.append(s, "system", "scenario.loaded", f"scenario:{seed}",
                      f"Loaded test case {seed}: {len(scenario.works)} works on {len(scenario.segments)} road segments",
                      {"seed": seed, "works": len(scenario.works), "segments": len(scenario.segments)})
    return scenario


def _is_stored(seed: int) -> bool:
    with session() as s:
        return store.get_scenario(s, seed) is not None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(init_db)
    app.state.wiring = build_wiring()
    app.state.seed = get_settings().scenario_seed
    app.state.tasks = set()
    if not await asyncio.to_thread(_is_stored, app.state.seed):
        await asyncio.to_thread(load_scenario, app, app.state.seed)
    yield
    for task in app.state.tasks:
        task.cancel()


app = FastAPI(title="MargaMitra API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_methods=["*"], allow_headers=["*"])
for r in (health, city, works, plans, ledger_router):
    app.include_router(r.router)
