"""Who implements what. Signatures are frozen; tests/test_interfaces.py checks every real function against these."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from contracts.models import (
    Approval,
    Conflict,
    CopilotReply,
    LedgerEntry,
    LedgerVerify,
    Metrics,
    NegotiationOutcome,
    ParallelGroup,
    Plan,
    PlanVariant,
    PolicyResult,
    RiskWindow,
    RunResult,
    Scenario,
    Segment,
    SolveConstraints,
    Work,
    WorkChange,
    WsEvent,
)

Emit = Callable[[WsEvent], Awaitable[None]]

# name -> "module:function" that must exist after the phase that builds it
IMPLEMENTATIONS: dict[str, str] = {
    # Track 4 · Saumya
    "generate_scenario": "data.scenario:generate_scenario",
    "load_segments": "data.segments:load_segments",
    "find_parallel_groups": "data.groups:find_parallel_groups",
    "compute_risk_windows": "risk.windows:compute_risk_windows",
    "affected_works": "risk.agent:affected_works",
    # Track 2 · Dhruv
    "solve": "solver.solve:solve",
    "naive_plan": "solver.baselines:naive_plan",
    "compute_metrics": "solver.metrics:compute_metrics",
    "plan_diff": "solver.diff:plan_diff",
    # Track 3 · Tanuj
    "detect_conflicts": "agents.conflicts:detect_conflicts",
    "negotiate": "agents.coordinator:negotiate",
    "start_run": "agents.workflow:start_run",
    "resume_run": "agents.workflow:resume_run",
    "run_copilot": "agents.copilot:run_copilot",
    "get_llm": "agents.llm:get_llm",
    # Track 1 · Nidhi
    "check_policy": "backend.app.policy_gate:check_policy",
}


def generate_scenario(seed: int) -> Scenario: ...
def load_segments() -> list[Segment]: ...
def find_parallel_groups(works: list[Work], segments: list[Segment]) -> list[ParallelGroup]: ...
def compute_risk_windows(scenario: Scenario, mode: str = "fixture", overrides: list[RiskWindow] | None = None) -> list[RiskWindow]: ...
def affected_works(scenario: Scenario, plan: Plan, windows: list[RiskWindow]) -> list[str]: ...
def solve(scenario: Scenario, constraints: SolveConstraints, variant: PlanVariant = PlanVariant.orchestrated) -> Plan: ...
def naive_plan(scenario: Scenario) -> Plan: ...
def compute_metrics(plan: Plan, scenario: Scenario) -> Metrics: ...
def plan_diff(old: Plan, new: Plan, scenario: Scenario) -> list[WorkChange]: ...
def detect_conflicts(scenario: Scenario, plan: Plan) -> list[Conflict]: ...
async def negotiate(scenario: Scenario, plan: Plan, conflicts: list[Conflict], run_id: str, emit: Emit) -> NegotiationOutcome: ...
def check_policy(plan: Plan, base: Plan | None, scenario: Scenario) -> PolicyResult: ...
async def start_run(deps: Deps, run_id: str, seed: int, reason: str = "orchestrate", base_plan_id: str | None = None) -> RunResult: ...
async def resume_run(deps: Deps, run_id: str, decision: str, by: str, reason: str | None = None) -> RunResult: ...
async def run_copilot(message: str, context: dict[str, Any], api_base: str, emit: Emit) -> CopilotReply: ...
def get_llm() -> LLMClient: ...


T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """agents/llm.py. Returns None when LLM_PROVIDER=none, on timeout or on a bad answer: the caller then uses its fallback."""
    provider: str

    async def structured(self, system: str, user: str, schema: type[T], model: str | None = None,
                         images: list[bytes] | None = None, max_tokens: int = 800) -> T | None: ...


class Ledger(Protocol):
    def append(self, actor: str, action: str, entity: str, summary: str, payload: dict[str, Any]) -> LedgerEntry: ...
    def verify(self) -> LedgerVerify: ...


@dataclass
class Deps:
    """Everything agents/workflow.py needs. The backend builds it from the real modules (or contracts.fakes in tests)."""
    generate_scenario: Callable[[int], Scenario]
    compute_risk_windows: Callable[..., list[RiskWindow]]
    affected_works: Callable[[Scenario, Plan, list[RiskWindow]], list[str]]
    naive_plan: Callable[[Scenario], Plan]
    solve: Callable[..., Plan]
    compute_metrics: Callable[[Plan, Scenario], Metrics]
    plan_diff: Callable[[Plan, Plan, Scenario], list[WorkChange]]
    detect_conflicts: Callable[[Scenario, Plan], list[Conflict]]
    negotiate: Callable[..., Awaitable[NegotiationOutcome]]
    check_policy: Callable[[Plan, Plan | None, Scenario], PolicyResult]
    save_plan: Callable[[Plan], Awaitable[None]]
    load_plan: Callable[[str], Awaitable[Plan | None]]  # a saved plan by id, None if unknown
    create_approval: Callable[[Plan, PolicyResult, str], Awaitable[Approval]]
    ledger_append: Callable[[str, str, str, str, dict[str, Any]], Awaitable[LedgerEntry]]
    emit: Emit
