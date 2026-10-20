"""The only place the backend reaches other tracks' functions: the real module when it exists, else contracts.fakes."""
import asyncio
import importlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from backend.app import ledger, store
from backend.app.config import get_settings
from backend.app.db import session
from backend.app.ids import next_id
from backend.app.policy_gate import check_policy
from backend.app.ws import hub
from contracts import fakes, interfaces
from contracts.interfaces import Deps
from contracts.models import (
    Approval,
    LedgerEntry,
    NegotiationMessage,
    Plan,
    PolicyResult,
    RiskWindow,
    RunResult,
    Scenario,
    WsEvent,
)

logger = logging.getLogger(__name__)

PURE = ["generate_scenario", "compute_risk_windows", "affected_works", "naive_plan", "solve", "compute_metrics",
        "plan_diff", "detect_conflicts", "negotiate"]
TIER_NAMES = {"auto": "Rules check", "department_officer": "Department officer", "ward_engineer": "Ward engineer",
              "commissioner": "Commissioner"}


def real_impl(name: str) -> Callable | None:
    module_name, func_name = interfaces.IMPLEMENTATIONS[name].split(":")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        # only a missing module means "not built yet"; a broken import inside a real module must surface
        if e.name and (module_name == e.name or module_name.startswith(e.name + ".")):
            return None
        raise
    return getattr(module, func_name)


@dataclass
class Wiring:
    deps: Deps
    pure_generate: Callable[[int], Scenario]
    start_run: Callable[..., Awaitable[RunResult]]
    resume_run: Callable[..., Awaitable[RunResult]]
    fakes: list[str]


def day_range(start: date, a: int, b: int) -> str:
    """'14–15 Nov' within a month, '30 Nov – 2 Dec' across months; both days inclusive."""
    d0, d1 = start + timedelta(days=a), start + timedelta(days=b)
    if d0 == d1:
        return f"{d1.day} {d1:%b}"
    if (d0.year, d0.month) == (d1.year, d1.month):
        return f"{d0.day}–{d1.day} {d1:%b}"
    return f"{d0.day} {d0:%b} – {d1.day} {d1:%b}"


def works_changed_text(n: int) -> str:
    return "1 work changes" if n == 1 else f"{n} works change"


def with_windows(deps: Deps, scenario: Scenario) -> Scenario:
    """The scenario with today's risk windows (forecast, overrides, events), as plans, rules and metrics expect."""
    return scenario.model_copy(update={"risk_windows": deps.compute_risk_windows(scenario)})


def _stored_scenario(seed: int, pure_generate: Callable[[int], Scenario]) -> Scenario:
    with session() as s:
        scenario = store.get_scenario(s, seed)
        if scenario is None:
            scenario = pure_generate(seed)
            store.put_scenario(s, scenario)
        return scenario


def _append(actor: str, action: str, entity: str, summary: str, payload: dict[str, Any]) -> LedgerEntry:
    with session() as s:
        return ledger.append(s, actor, action, entity, summary, payload)


async def ledger_append(actor: str, action: str, entity: str, summary: str, payload: dict[str, Any]) -> LedgerEntry:
    entry = await asyncio.to_thread(_append, actor, action, entity, summary, payload)
    await hub.broadcast(WsEvent(type="ledger.appended", data=entry.model_dump(mode="json"), ts=datetime.now(UTC)))
    return entry


async def emit(event: WsEvent) -> None:
    if event.type == "negotiation.message":
        msg = NegotiationMessage.model_validate(event.data)
        await asyncio.to_thread(in_session, store.save_message, msg)
    await hub.broadcast(event)


def in_session(fn: Callable, *args: Any) -> Any:
    with session() as s:
        return fn(s, *args)


async def save_plan(plan: Plan) -> None:
    await asyncio.to_thread(in_session, store.save_plan, plan)


async def load_plan(plan_id: str) -> Plan | None:
    return await asyncio.to_thread(in_session, store.get_plan, plan_id)


def _db_deps(pure: dict[str, Callable]) -> Deps:
    # shortcut: short sync reads in the event loop, fine for one API process
    def generate_scenario(seed: int) -> Scenario:
        return _stored_scenario(seed, pure["generate_scenario"])

    def compute_risk_windows(scenario: Scenario, mode: str | None = None,
                             overrides: list[RiskWindow] | None = None) -> list[RiskWindow]:
        stored = in_session(store.list_windows, scenario.seed)
        return pure["compute_risk_windows"](scenario, mode or get_settings().weather_mode, stored + (overrides or []))

    def _new_approval(plan: Plan, result: PolicyResult, run_id: str) -> Approval:
        scenario = generate_scenario(plan.seed)
        with session() as s:
            approval = Approval(
                approval_id=next_id(s, "A"), plan_id=plan.plan_id, run_id=run_id, tier=result.tier, status="pending",
                summary=f"New plan for {day_range(scenario.start_date, 0, scenario.horizon_days - 1)} · "
                        f"{works_changed_text(result.works_changed)}",
                requested_at=datetime.now(UTC))
            store.add_approval(s, approval)
        return approval

    async def create_approval(plan: Plan, result: PolicyResult, run_id: str) -> Approval:
        approval = await asyncio.to_thread(_new_approval, plan, result, run_id)
        await ledger_append("rules", "approval.requested", f"plan:{plan.plan_id}",
                            f"Sent for approval: {TIER_NAMES[approval.tier]}",
                            {"approval_id": approval.approval_id, "tier": approval.tier, "run_id": run_id})
        return approval

    return Deps(
        generate_scenario=generate_scenario, compute_risk_windows=compute_risk_windows,
        affected_works=pure["affected_works"], naive_plan=pure["naive_plan"], solve=pure["solve"],
        compute_metrics=pure["compute_metrics"], plan_diff=pure["plan_diff"], detect_conflicts=pure["detect_conflicts"],
        negotiate=pure["negotiate"], check_policy=check_policy, save_plan=save_plan, load_plan=load_plan,
        create_approval=create_approval, ledger_append=ledger_append, emit=emit,
    )


def build_wiring() -> Wiring:
    stand_ins = fakes.fake_deps()
    used_fakes: list[str] = []

    def pick(name: str, fake: Callable) -> Callable:
        real = real_impl(name)
        if real is None:
            used_fakes.append(name)
        return real or fake

    pure = {name: pick(name, getattr(stand_ins, name)) for name in PURE}
    start_run = pick("start_run", fakes.fake_start_run)
    resume_run = pick("resume_run", fakes.fake_resume_run)
    if used_fakes:
        logger.info("Using stand-ins for: %s", ", ".join(used_fakes))
    return Wiring(deps=_db_deps(pure), pure_generate=pure["generate_scenario"], start_run=start_run,
                  resume_run=resume_run, fakes=used_fakes)
