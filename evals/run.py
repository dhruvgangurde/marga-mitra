"""Plan every test case in the five ways of the Impact page and summarize the results."""
from __future__ import annotations

import os
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from contracts import fakes, rules
from contracts.models import (
    NegotiationOutcome,
    Plan,
    PlanVariant,
    RiskKind,
    RiskWindow,
    Scenario,
    SolveConstraints,
    WsEvent,
)
from evals.imports import optional
from solver.solve import days_text, solve


@dataclass
class Parts:
    generate_scenario: Callable[[int], Scenario]
    compute_risk_windows: Callable[..., list[RiskWindow]] | None
    negotiate: Callable[..., Awaitable[NegotiationOutcome]]
    stand_ins: list[str]


def load_parts(use_real: bool = True) -> Parts:
    """The merged modules of the other tracks, else the stand-ins from contracts.fakes."""
    stand_ins: list[str] = []

    def pick(module: str, name: str, stand_in: Any) -> Any:
        found = optional(module, name) if use_real else None
        if found is None:
            stand_ins.append(module)
            return stand_in
        return found

    return Parts(generate_scenario=pick("data.scenario", "generate_scenario", fakes.tiny_scenario),
                 compute_risk_windows=pick("risk.windows", "compute_risk_windows", None),
                 negotiate=pick("agents.coordinator", "negotiate", fakes.fake_negotiate),
                 stand_ins=stand_ins)


def rain_spell(scenario: Scenario) -> RiskWindow:
    """Two days of heavy rain, the same for all five variants. Test case 1 gets the demo's rain on 14–15 Nov."""
    start = 12 if scenario.seed == 1 else random.Random(scenario.seed * 7919).randint(5, 20)
    end = start + 1
    return RiskWindow(window_id=f"EVAL-RAIN-{scenario.seed}", kind=RiskKind.rain, start_day=start, end_day=end,
                      segment_ids=[], value=70.0, source="override",
                      label=f"Heavy rain, {days_text(scenario, start, end)}")


def eval_windows(scenario: Scenario, parts: Parts, with_rain: bool = True) -> list[RiskWindow]:
    spell = [rain_spell(scenario)] if with_rain else []
    if parts.compute_risk_windows is not None:
        return parts.compute_risk_windows(scenario, "fixture", overrides=spell or None)
    low = sorted(s.segment_id for s in scenario.segments if s.low_lying)
    return [*scenario.risk_windows, *(w.model_copy(update={"segment_ids": low}) for w in spell)]


def with_windows(scenario: Scenario, windows: list[RiskWindow]) -> Scenario:
    return scenario.model_copy(update={"risk_windows": windows})


VARIANTS = ("naive", "solver_only", "agents", "risk", "full")
LABELS = {
    "naive": "Old way (first come, first dug)",
    "solver_only": "Scheduler without agents",
    "agents": "+ department agents",
    "risk": "+ rain, air and event forecasts",
    "full": "+ photo checks (all of MargaMitra)",
}


def force_no_llm() -> None:
    """The negotiation runs without a model, so the numbers repeat and cost nothing."""
    os.environ["LLM_PROVIDER"] = "none"
    get_llm = optional("agents.llm", "get_llm")
    if get_llm is not None:
        get_llm.cache_clear()


async def _drop(event: WsEvent) -> None:
    """The evaluation does not need live events."""


async def _negotiated(scenario: Scenario, parts: Parts, naive: Plan, run_id: str) -> SolveConstraints:
    out = await parts.negotiate(scenario, naive, rules.find_clashes(scenario, naive), run_id, _drop)
    return out.constraints


async def plan_variant(variant: str, scenario: Scenario, parts: Parts, naive: Plan) -> Plan:
    """One of the five plans. Every variant is measured later on the same stormy scenario; only the planning changes."""
    calm = with_windows(scenario, [])
    if variant == "naive":
        return naive
    if variant == "solver_only":
        return solve(calm, SolveConstraints(use_risk=False, use_groups=False), PlanVariant.solver_only)
    if variant == "agents":
        agreed = await _negotiated(calm, parts, naive, f"EVAL-{scenario.seed}-agents")
        return solve(calm, agreed.model_copy(update={"use_risk": False}), PlanVariant.agents)
    if variant in ("risk", "full"):  # photo checks move no dates; their effect is the fake-repair count
        stormy = with_windows(scenario, eval_windows(scenario, parts))
        agreed = await _negotiated(stormy, parts, naive, f"EVAL-{scenario.seed}-risk")
        return solve(stormy, agreed.model_copy(update={"use_risk": True}), PlanVariant.orchestrated)
    raise ValueError(f"unknown variant: {variant}")


def parse_seeds(text: str) -> list[int]:
    """'1-50' or '1-3,7': comma-separated seeds and inclusive ranges, sorted without duplicates."""
    if not text.strip():
        raise ValueError("no seeds")
    seeds: set[int] = set()
    for item in text.split(","):
        first, sep, last = item.strip().partition("-")
        start = int(first)
        end = int(last) if sep else start
        if end < start:
            raise ValueError(f"range ends before it starts: {item.strip()}")
        if start < 1:
            raise ValueError(f"seeds start at 1: {item.strip()}")
        seeds.update(range(start, end + 1))
    return sorted(seeds)
