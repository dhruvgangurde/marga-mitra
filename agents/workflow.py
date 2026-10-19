"""The planning run: forecasts, clashes, negotiation, scheduler, rules check, then a pause until a person decides."""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agents import conflicts as conflict_finder
from agents import coordinator
from agents.department import DEPT_NAMES
from agents.tools import days_label
from contracts import costs
from contracts.fakes import MemoryStore, fake_deps
from contracts.interfaces import Deps
from contracts.models import (
    Conflict,
    Metrics,
    NegotiationMessage,
    NegotiationOutcome,
    Plan,
    PlanStatus,
    PlanVariant,
    PolicyResult,
    RiskWindow,
    RunResult,
    Scenario,
    SolveConstraints,
    WsEvent,
)

logger = logging.getLogger(__name__)
FAILED_NOTE = "The plan could not be made."


class RunState(TypedDict, total=False):
    run_id: str
    seed: int
    reason: str
    base_plan_id: str | None
    plan_label: str
    windows: list[dict[str, Any]]
    base: dict[str, Any]
    affected: list[str] | None  # None means every work (a full orchestrate run)
    conflicts: list[dict[str, Any]]
    outcome: dict[str, Any]
    plan: dict[str, Any]
    metrics: dict[str, Any]
    base_metrics: dict[str, Any]
    policy: dict[str, Any]
    approval_id: str
    decision: dict[str, Any]
    status: str


# the backend passes an AsyncPostgresSaver (DATABASE_URL with postgresql+psycopg:// changed to postgresql://, after
# await saver.setup()) so a paused run survives an API restart
_saver: Any = InMemorySaver()
_compiled: Any = None
_deps: dict[str, Deps] = {}


def set_checkpointer(saver: Any) -> None:
    global _saver, _compiled
    _saver = saver
    _compiled = None


def _now() -> datetime:
    return datetime.now(UTC)


def _deps_of(config: RunnableConfig) -> Deps:
    return _deps[config["configurable"]["thread_id"]]


def _scenario(deps: Deps, state: RunState) -> Scenario:
    scenario = deps.generate_scenario(state["seed"])
    if "windows" not in state:
        return scenario
    return scenario.model_copy(update={"risk_windows": [RiskWindow.model_validate(w) for w in state["windows"]]})


def _plan_id(run_id: str) -> str:
    return "P-" + run_id.removeprefix("RUN-")


def _grouped(value: Any) -> str:
    return costs.inr(round(value)).removeprefix("₹")


def decision_body(b: Metrics, n: Metrics) -> str:
    body = (f"The new plan: digs per road {b.digs_per_road:.1f} → {n.digs_per_road:.1f}, lane-closure hours "
            f"{_grouped(b.lane_closure_hours)} → {_grouped(n.lane_closure_hours)}, clashes {b.clashes} → {n.clashes}.")
    if b.trench_hours_in_rain or n.trench_hours_in_rain:
        body += f" Trench-hours in rain: {_grouped(b.trench_hours_in_rain)} → {_grouped(n.trench_hours_in_rain)}."
    return body


def _emergency_reach(scenario: Scenario, base: Plan) -> set[str]:
    """Every emergency work, and the works planned on its roads on the days it asked for."""
    reach: set[str] = set()
    planned = {a.work_id: a for a in base.assignments}
    for emergency in (w for w in scenario.works if w.is_emergency):
        reach.add(emergency.work_id)
        asked_end = emergency.requested_start + emergency.modes[0].duration_days - 1
        for w in scenario.works:
            a = planned.get(w.work_id)
            if (a is not None and set(w.segment_ids) & set(emergency.segment_ids)
                    and a.start_day <= asked_end and a.end_day >= emergency.requested_start):
                reach.add(w.work_id)
    return reach


def settle(c: SolveConstraints, base: Plan, scenario: Scenario, affected: list[str] | None) -> SolveConstraints:
    """Keep the negotiated constraints only where the run may change something."""
    pinned, low, forbidden = dict(c.pinned_start), dict(c.min_start), dict(c.forbidden_days)
    groups = list(c.shared_groups)
    works = {w.work_id: w for w in scenario.works}
    if affected is not None:
        touched = set(affected)
        planned = {a.work_id: a for a in base.assignments}
        for w in scenario.works:
            if w.done or w.work_id in touched or w.work_id not in planned:
                continue
            pinned[w.work_id] = planned[w.work_id].start_day
            low.pop(w.work_id, None)
            forbidden.pop(w.work_id, None)
        groups = [g for g in groups if _group_stays(g, scenario, touched)]
        for g in scenario.parallel_groups:
            if g.group_id not in groups and _already_shared(g.group_id, g.work_ids, planned, touched):
                groups.append(g.group_id)
    emergencies = {w.work_id for w in works.values() if w.is_emergency}
    for work_id in emergencies:
        pinned.pop(work_id, None)
        low.pop(work_id, None)
        forbidden.pop(work_id, None)
    groups = [g for g in groups if not _group_ids(g, scenario) & emergencies]
    return c.model_copy(update={"pinned_start": pinned, "min_start": low, "forbidden_days": forbidden,
                                "shared_groups": groups})


def _group_ids(group_id: str, scenario: Scenario) -> set[str]:
    return {w for g in scenario.parallel_groups if g.group_id == group_id for w in g.work_ids}


def _group_stays(group_id: str, scenario: Scenario, touched: set[str]) -> bool:
    return _group_ids(group_id, scenario) <= touched


def _already_shared(group_id: str, work_ids: list[str], planned: dict[str, Any], touched: set[str]) -> bool:
    return (not set(work_ids) & touched
            and all(w in planned and planned[w].shared_group == group_id for w in work_ids))


async def load(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    scenario = _deps_of(config).generate_scenario(state["seed"])
    return {"plan_label": f"the plan for {days_label(scenario, 0, scenario.horizon_days - 1)}"}


async def risk(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    windows = deps.compute_risk_windows(deps.generate_scenario(state["seed"]))
    return {"windows": [w.model_dump(mode="json") for w in windows]}


async def baseline(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    scenario = _scenario(deps, state)
    base_id = state.get("base_plan_id")
    base = (await deps.load_plan(base_id) if base_id else None) or deps.naive_plan(scenario)
    affected: list[str] | None = None
    if state["reason"] != "orchestrate":
        windows = [RiskWindow.model_validate(w) for w in state["windows"]]
        ids = set(deps.affected_works(scenario, base, windows))
        if state["reason"] == "emergency":
            ids |= _emergency_reach(scenario, base)
        affected = sorted(ids)
    return {"base": base.model_dump(mode="json"), "affected": affected}


async def find_conflicts(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    found = deps.detect_conflicts(_scenario(deps, state), Plan.model_validate(state["base"]))
    if state["affected"] is not None:
        touched = set(state["affected"])
        found = [c for c in found if touched & set(c.work_ids)]
    return {"conflicts": [c.model_dump(mode="json") for c in found]}


async def negotiate(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    scenario = _scenario(deps, state)
    base = Plan.model_validate(state["base"])
    conflicts = [Conflict.model_validate(c) for c in state["conflicts"]]
    outcome = await deps.negotiate(scenario, base, conflicts, state["run_id"], deps.emit)
    constraints = settle(outcome.constraints, base, scenario, state["affected"])
    return {"outcome": outcome.model_copy(update={"constraints": constraints}).model_dump(mode="json")}


async def solve(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    scenario = _scenario(deps, state)
    constraints = NegotiationOutcome.model_validate(state["outcome"]).constraints
    plan = deps.solve(scenario, constraints, PlanVariant.orchestrated)
    base_id = state.get("base_plan_id") or state["base"]["plan_id"]
    plan = plan.model_copy(update={"plan_id": _plan_id(state["run_id"]), "base_plan_id": base_id})
    return {"plan": plan.model_dump(mode="json")}


async def decide_message(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    scenario = _scenario(deps, state)
    plan, base = Plan.model_validate(state["plan"]), Plan.model_validate(state["base"])
    outcome = NegotiationOutcome.model_validate(state["outcome"])
    metrics, base_metrics = deps.compute_metrics(plan, scenario), deps.compute_metrics(base, scenario)
    message = NegotiationMessage(
        msg_id=f"M{len(outcome.messages) + 1:03d}", run_id=state["run_id"], round=max(1, outcome.rounds),
        sender="solver", recipients=["Everyone"], type="DECISION",
        work_ids=[ch.work_id for ch in deps.plan_diff(base, plan, scenario)],
        body=decision_body(base_metrics, metrics), ts=_now())
    await deps.emit(WsEvent(type="negotiation.message", data=message.model_dump(mode="json"), ts=_now()))
    return {"metrics": metrics.model_dump(mode="json"), "base_metrics": base_metrics.model_dump(mode="json")}


async def rules(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    policy = deps.check_policy(Plan.model_validate(state["plan"]), Plan.model_validate(state["base"]),
                               _scenario(deps, state))
    return {"policy": policy.model_dump(mode="json")}


async def request_approval(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    plan = Plan.model_validate(state["plan"]).model_copy(update={"status": PlanStatus.waiting_approval})
    policy = PolicyResult.model_validate(state["policy"])
    entity = f"plan:{plan.plan_id}"
    await deps.save_plan(plan)
    await deps.ledger_append(
        "scheduler", "plan.decided", entity, f"Scheduler made a new plan: {policy.works_changed} works change",
        {"run_id": state["run_id"], "plan_id": plan.plan_id, "base_plan_id": plan.base_plan_id,
         "metrics": state["metrics"]})
    failed = "; ".join(c.detail for c in policy.checks if c.severity == "fail")
    await deps.ledger_append("rules", "rules.checked", entity,
                             "Rules check passed" if policy.passed else f"Rules check failed: {failed}", state["policy"])
    approval = await deps.create_approval(plan, policy, state["run_id"])
    await deps.emit(WsEvent(type="approval.requested", data=approval.model_dump(mode="json"), ts=_now()))
    return {"plan": plan.model_dump(mode="json"), "approval_id": approval.approval_id}


async def wait(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    # this node runs again from its start on resume, so it does nothing else
    return {"decision": interrupt({"approval_id": state["approval_id"], "plan_id": state["plan"]["plan_id"]})}


async def apply(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps_of(config)
    plan = Plan.model_validate(state["plan"])
    decision = state["decision"]
    entity = f"plan:{plan.plan_id}"
    payload = {"run_id": state["run_id"], "approval_id": state["approval_id"]}
    if decision["decision"] == "approve":
        plan = plan.model_copy(update={"status": PlanStatus.approved})
        await deps.save_plan(plan)
        await deps.ledger_append(decision["by"], "plan.approved", entity, f"Approved {state['plan_label']}", payload)
    else:
        reason = decision.get("reason")
        plan = plan.model_copy(update={"status": PlanStatus.rejected})
        await deps.save_plan(plan)
        await deps.ledger_append(decision["by"], "plan.rejected", entity,
                                 f"Rejected {state['plan_label']}" + (f": {reason}" if reason else ""),
                                 {**payload, "reason": reason})
    status = "approved" if decision["decision"] == "approve" else "rejected"
    return {"plan": plan.model_dump(mode="json"), "status": status}


def _app() -> Any:
    global _compiled
    if _compiled is None:
        graph = StateGraph(RunState)
        steps = [("load", load), ("risk", risk), ("baseline", baseline), ("conflicts", find_conflicts),
                 ("negotiate", negotiate), ("solve", solve), ("decide_message", decide_message), ("rules", rules),
                 ("request_approval", request_approval), ("wait", wait), ("apply", apply)]
        for name, node in steps:
            graph.add_node(name, node)
        graph.add_edge(START, steps[0][0])
        for (a, _), (b, _) in zip(steps, steps[1:], strict=False):
            graph.add_edge(a, b)
        graph.add_edge(steps[-1][0], END)
        _compiled = graph.compile(checkpointer=_saver)
    return _compiled


def _config(run_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": run_id}}


def _result(run_id: str, status: str, out: dict[str, Any]) -> RunResult:
    return RunResult(run_id=run_id, status=status, plan_id=out["plan"]["plan_id"], approval_id=out["approval_id"],
                     metrics=Metrics.model_validate(out["metrics"]))


async def start_run(deps: Deps, run_id: str, seed: int, reason: str = "orchestrate",
                    base_plan_id: str | None = None) -> RunResult:
    _deps[run_id] = deps
    failed = RunResult(run_id=run_id, status="failed", note=FAILED_NOTE)
    try:
        out = await _app().ainvoke({"run_id": run_id, "seed": seed, "reason": reason, "base_plan_id": base_plan_id},
                                   _config(run_id))
    except Exception:
        logger.exception("run %s failed", run_id)
        return failed
    finally:
        _deps.pop(run_id, None)
    if "__interrupt__" not in out:
        logger.error("run %s ended without waiting for approval", run_id)
        return failed
    unplanned = len(out["plan"]["unplanned"])
    result = _result(run_id, "waiting_approval", out)
    return result.model_copy(update={"note": f"{unplanned} works could not be planned." if unplanned else ""})


async def resume_run(deps: Deps, run_id: str, decision: str, by: str, reason: str | None = None) -> RunResult:
    if decision not in ("approve", "reject"):
        raise ValueError(f"Unknown decision {decision!r}.")
    snapshot = await _app().aget_state(_config(run_id))
    if "wait" not in snapshot.next:
        raise ValueError(f"Run {run_id} is not waiting for approval.")
    _deps[run_id] = deps
    try:
        out = await _app().ainvoke(Command(resume={"decision": decision, "by": by, "reason": reason}), _config(run_id))
    finally:
        _deps.pop(run_id, None)
    return _result(run_id, out["status"], out)


SENDER_NAMES = {**DEPT_NAMES, "coordinator": "Coordinator", "solver": "Scheduler"}


def _demo_deps(store: MemoryStore) -> Deps:
    deps = fake_deps(store)
    deps.detect_conflicts = conflict_finder.detect_conflicts
    deps.negotiate = coordinator.negotiate
    try:
        from solver.baselines import naive_plan
        from solver.diff import plan_diff
        from solver.metrics import compute_metrics
        from solver.solve import solve
    except ImportError:
        return deps  # the scheduler has not landed yet; the stand-ins keep the demo running
    deps.naive_plan, deps.solve, deps.compute_metrics, deps.plan_diff = naive_plan, solve, compute_metrics, plan_diff
    return deps


def _show(event: WsEvent) -> None:
    d = event.data
    if event.type == "negotiation.message":
        print(f"{d['msg_id']}  {d['type']:<8} {SENDER_NAMES[d['sender']]} → {', '.join(d['recipients'])}: {d['body']}")
    elif event.type == "approval.requested":
        print(f"Waiting for approval {d['approval_id']} ({d['tier']})")


async def demo() -> None:
    store = MemoryStore()
    deps = _demo_deps(store)

    async def emit(event: WsEvent) -> None:
        await store.emit(event)
        _show(event)

    deps.emit = emit
    await start_run(deps, "RUN-DEMO", 1)
    await resume_run(deps, "RUN-DEMO", "approve", "ward_engineer")
    print("Approved: plan P-DEMO")
    for entry in store.ledger:
        print(f"#{entry.seq} {entry.actor} {entry.action}: {entry.summary}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m agents.workflow")
    parser.add_argument("--demo", action="store_true", required=True, help="run one planning run with its approval")
    parser.parse_args(argv)
    asyncio.run(demo())


if __name__ == "__main__":
    main()
