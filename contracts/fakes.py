"""Small working stand-ins so every track can run and test alone before the real modules exist."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any

from contracts import costs
from contracts.interfaces import Deps, Emit
from contracts.models import (
    Approval,
    Assignment,
    Conflict,
    ConflictKind,
    CopilotReply,
    CopilotStep,
    Dept,
    LedgerEntry,
    Metrics,
    Mode,
    NegotiationMessage,
    NegotiationOutcome,
    ParallelGroup,
    Plan,
    PlanStatus,
    PlanVariant,
    PolicyResult,
    RiskKind,
    RiskWindow,
    RoadClass,
    RunResult,
    Scenario,
    Segment,
    SolveConstraints,
    Work,
    WsEvent,
)


def now() -> datetime:
    return datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


def _seg(i: int, lon: float, low: bool = False) -> Segment:
    return Segment(segment_id=f"S-{i:04d}", osm_way_id=1000 + i, name="Test Road", road_class=RoadClass.secondary,
                   length_m=200.0, lanes=2, traffic_weight=3.0, elevation_m=8.0 if low else 30.0, low_lying=low,
                   neighbors=[f"S-{j:04d}" for j in (i - 1, i + 1) if 1 <= j <= 3],
                   coords=[(lon, 13.01), (lon + 0.002, 13.01)])


def _work(wid: str, dept: Dept, segs: list[str], start: int, dur: int, title: str, depends: list[str] | None = None) -> Work:
    length = 200.0 * len(segs)
    modes = [costs.mode_option(dept, length, Mode.open_cut, dur, 1)]
    if dept in (Dept.telecom, Dept.power, Dept.gas):
        modes.append(costs.mode_option(dept, length, Mode.trenchless, dur + 1, 0))
    return Work(work_id=wid, dept=dept, title=title, road_name="Test Road", segment_ids=segs, length_m=length,
                requested_start=start, earliest_start=0, latest_end=27, modes=modes, depends_on=depends or [],
                deposit_inr=costs.deposit_inr(dept, length, Mode.open_cut))


def tiny_scenario(seed: int = 0) -> Scenario:
    segs = [_seg(1, 74.79), _seg(2, 74.792, low=True), _seg(3, 74.794)]
    works = [
        _work("W-001", Dept.water, ["S-0001", "S-0002"], 8, 5, "Water main"),
        _work("T-001", Dept.telecom, ["S-0001", "S-0002"], 10, 3, "Fibre duct"),
        _work("G-001", Dept.gas, ["S-0003"], 9, 4, "Gas line"),
        _work("R-001", Dept.roads, ["S-0001", "S-0002", "S-0003"], 9, 3, "Resurfacing", depends=["W-001", "T-001", "G-001"]),
    ]
    group = ParallelGroup(group_id="G1", work_ids=["W-001", "T-001"], segment_ids=["S-0001", "S-0002"],
                          saving_inr=costs.shared_trench_saving_inr(works[:2]))
    rain = RiskWindow(window_id="R1", kind=RiskKind.rain, start_day=12, end_day=13, segment_ids=["S-0002"], value=70.0,
                      source="fixture", label="Heavy rain, 14–15 Nov")
    return Scenario(seed=seed, start_date=date(2026, 11, 2), segments=segs, works=works, risk_windows=[rain],
                    parallel_groups=[group])


def fake_naive_plan(scenario: Scenario) -> Plan:
    a = [Assignment(work_id=w.work_id, start_day=w.requested_start, end_day=w.requested_start + w.modes[0].duration_days - 1,
                    mode=w.modes[0].mode, reason="As the department asked.") for w in scenario.works]
    return Plan(plan_id="P-NAIVE", seed=scenario.seed, variant=PlanVariant.naive, created_at=now(), assignments=a)


def fake_solve(scenario: Scenario, constraints: SolveConstraints, variant: PlanVariant = PlanVariant.orchestrated) -> Plan:
    plan = fake_naive_plan(scenario)
    return plan.model_copy(update={"plan_id": "P-FAKE", "variant": variant})


def fake_metrics(plan: Plan, scenario: Scenario) -> Metrics:
    return Metrics(plan_id=plan.plan_id, excavations=len(plan.assignments), digs_per_road=1.0, lane_closure_hours=0.0,
                   trench_hours_in_rain=0.0, clashes=0, days_late=0.0, cost_inr=0, dust_score=0.0)


def fake_conflicts(scenario: Scenario, plan: Plan) -> list[Conflict]:
    return [Conflict(conflict_id="C1", kind=ConflictKind.same_road, work_ids=["W-001", "T-001"], segment_ids=["S-0001"],
                     start_day=10, end_day=12, note="2 works on Test Road at the same time")]


async def fake_negotiate(scenario: Scenario, plan: Plan, conflicts: list[Conflict], run_id: str, emit: Emit) -> NegotiationOutcome:
    msg = NegotiationMessage(msg_id="M1", run_id=run_id, round=1, sender="coordinator", recipients=["water", "telecom"],
                             type="NOTICE", work_ids=["W-001", "T-001"], body="2 works clash on Test Road.", ts=now())
    await emit(WsEvent(type="negotiation.message", data=msg.model_dump(mode="json"), ts=now()))
    return NegotiationOutcome(run_id=run_id, rounds=1, messages=[msg], constraints=SolveConstraints(), used_llm=False)


def fake_policy(plan: Plan, base: Plan | None, scenario: Scenario) -> PolicyResult:
    return PolicyResult(plan_id=plan.plan_id, passed=True, checks=[], tier="ward_engineer", works_changed=0, cost_delta_inr=0)


class MemoryStore:
    """In-memory stand-in for the backend's database, with a hash-chained ledger like the real one."""

    def __init__(self) -> None:
        self.plans: dict[str, Plan] = {}
        self.approvals: dict[str, Approval] = {}
        self.ledger: list[LedgerEntry] = []
        self.events: list[WsEvent] = []

    async def save_plan(self, plan: Plan) -> None:
        self.plans[plan.plan_id] = plan

    async def load_plan(self, plan_id: str) -> Plan | None:
        return self.plans.get(plan_id)

    async def create_approval(self, plan: Plan, result: PolicyResult, run_id: str) -> Approval:
        ap = Approval(approval_id=f"A-{len(self.approvals) + 1:04d}", plan_id=plan.plan_id, run_id=run_id, tier=result.tier,
                      status="pending", summary=f"New plan {plan.plan_id}", requested_at=now())
        self.approvals[ap.approval_id] = ap
        return ap

    async def ledger_append(self, actor: str, action: str, entity: str, summary: str, payload: dict[str, Any]) -> LedgerEntry:
        prev = self.ledger[-1].hash if self.ledger else "0" * 64
        seq = len(self.ledger) + 1
        body = json.dumps({"seq": seq, "actor": actor, "action": action, "entity": entity, "summary": summary,
                           "payload": payload, "prev_hash": prev}, sort_keys=True, ensure_ascii=False)
        entry = LedgerEntry(seq=seq, ts=now(), actor=actor, action=action, entity=entity, summary=summary, payload=payload,
                            prev_hash=prev, hash=hashlib.sha256(body.encode()).hexdigest())
        self.ledger.append(entry)
        return entry

    async def emit(self, event: WsEvent) -> None:
        self.events.append(event)


def fake_deps(store: MemoryStore | None = None) -> Deps:
    s = store or MemoryStore()
    return Deps(
        generate_scenario=tiny_scenario,
        compute_risk_windows=lambda scenario, mode="fixture", overrides=None: list(scenario.risk_windows) + list(overrides or []),
        affected_works=lambda scenario, plan, windows: ["W-001"],
        naive_plan=fake_naive_plan,
        solve=fake_solve,
        compute_metrics=fake_metrics,
        plan_diff=lambda old, new, scenario: [],
        detect_conflicts=fake_conflicts,
        negotiate=fake_negotiate,
        check_policy=fake_policy,
        save_plan=s.save_plan,
        load_plan=s.load_plan,
        create_approval=s.create_approval,
        ledger_append=s.ledger_append,
        emit=s.emit,
    )


async def fake_start_run(deps: Deps, run_id: str, seed: int, reason: str = "orchestrate", base_plan_id: str | None = None) -> RunResult:
    """The workflow without LangGraph: baseline, clashes, negotiation, plan, rules, then wait for approval."""
    scenario = deps.generate_scenario(seed)
    base = (await deps.load_plan(base_plan_id) if base_plan_id else None) or deps.naive_plan(scenario)
    outcome = await deps.negotiate(scenario, base, deps.detect_conflicts(scenario, base), run_id, deps.emit)
    plan = deps.solve(scenario, outcome.constraints).model_copy(update={"status": PlanStatus.waiting_approval})
    await deps.save_plan(plan)
    result = deps.check_policy(plan, base, scenario)
    approval = await deps.create_approval(plan, result, run_id)
    await deps.ledger_append("scheduler", "plan.decided", f"plan:{plan.plan_id}", "Scheduler made a new plan", {"run_id": run_id})
    await deps.emit(WsEvent(type="approval.requested", data=approval.model_dump(mode="json"), ts=now()))
    return RunResult(run_id=run_id, status="waiting_approval", plan_id=plan.plan_id, approval_id=approval.approval_id,
                     metrics=deps.compute_metrics(plan, scenario))


async def fake_resume_run(deps: Deps, run_id: str, decision: str, by: str, reason: str | None = None) -> RunResult:
    status = "approved" if decision == "approve" else "rejected"
    await deps.ledger_append(by, f"plan.{status}", f"run:{run_id}", f"Plan {status} by {by}", {"reason": reason})
    return RunResult(run_id=run_id, status=status)


async def fake_run_copilot(message: str, context: dict[str, Any], api_base: str, emit: Emit) -> CopilotReply:
    step = CopilotStep(step_id="S1", text="Reading your question", status="done")
    await emit(WsEvent(type="copilot.step", data=step.model_dump(mode="json"), ts=now()))
    return CopilotReply(reply_id="CP-1", text="The copilot is not connected yet.", steps=[step], used_llm=False)
