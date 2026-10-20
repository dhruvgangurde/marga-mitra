"""Plan every test case in the five ways of the Impact page and summarize the results.

    python -m evals.run                          # test cases 1 to 50, writes evals/results/summary.json and runs.csv
    python -m evals.run --seeds 1-3 --fixed-time # a quick run with a fixed generated_at
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contracts import costs, fakes, rules
from contracts.models import (
    EvalRow,
    EvalSummary,
    Metrics,
    NegotiationOutcome,
    Plan,
    PlanVariant,
    RiskKind,
    RiskWindow,
    Scenario,
    SolveConstraints,
    Stat,
    WsEvent,
)
from evals import fake_repairs
from evals.fake_repairs import FakeRepairResult
from evals.imports import optional
from evals.stats import stat
from solver.baselines import naive_plan
from solver.metrics import compute_metrics
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
        return await risk_plan(scenario, parts, naive, eval_windows(scenario, parts), f"EVAL-{scenario.seed}-risk")
    raise ValueError(f"unknown variant: {variant}")


async def risk_plan(scenario: Scenario, parts: Parts, naive: Plan, windows: list[RiskWindow], run_id: str) -> Plan:
    """Negotiate and plan with these risk windows switched on."""
    stormy = with_windows(scenario, windows)
    agreed = await _negotiated(stormy, parts, naive, run_id)
    return solve(stormy, agreed.model_copy(update={"use_risk": True}), PlanVariant.orchestrated)


CSV_FIELDS = ("seed", "variant", "plan_id", "excavations", "digs_per_road", "lane_closure_hours", "trench_hours_in_rain",
              "clashes", "days_late", "cost_inr", "dust_score")
ROW_FIELDS = ("digs_per_road", "lane_closure_hours", "trench_hours_in_rain", "clashes", "days_late", "cost_inr")


@dataclass
class Evaluation:
    metrics: dict[str, list[Metrics]]  # variant -> one Metrics per seed, in seed order
    csv_rows: list[dict[str, object]]
    seconds: dict[str, float]  # variant -> total planning time


async def evaluate(seeds: list[int], parts: Parts) -> Evaluation:
    force_no_llm()
    ev = Evaluation(metrics={v: [] for v in VARIANTS}, csv_rows=[], seconds=dict.fromkeys(VARIANTS, 0.0))
    for seed in seeds:
        scenario = parts.generate_scenario(seed)
        stormy = with_windows(scenario, eval_windows(scenario, parts))
        naive = naive_plan(scenario)
        plans: dict[str, Plan] = {}
        for variant in VARIANTS:
            t0 = time.perf_counter()
            plans[variant] = plans["risk"] if variant == "full" else await plan_variant(variant, scenario, parts, naive)
            ev.seconds[variant] += time.perf_counter() - t0
            m = compute_metrics(plans[variant], stormy)
            ev.metrics[variant].append(m)
            ev.csv_rows.append({"seed": seed, "variant": variant, **m.model_dump(include=set(CSV_FIELDS))})
    return ev


def summarize(ev: Evaluation, seeds: list[int], fake: FakeRepairResult, generated_at: datetime) -> EvalSummary:
    rows = [EvalRow(variant=v, **{f: stat([float(getattr(m, f)) for m in ev.metrics[v]]) for f in ROW_FIELDS})
            for v in VARIANTS]
    return EvalSummary(seeds=seeds, rows=rows, fake_repairs_caught=fake.caught, fake_repairs_total=fake.total,
                       generated_at=generated_at)


def write_summary(summary: EvalSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _cell(s: Stat, show: Callable[[float], str]) -> str:
    return f"{show(s.median)} ({show(s.low)}–{show(s.high)})"


def table(summary: EvalSummary) -> str:
    one = "{:.1f}".format
    hours = "{:,.0f}".format

    def money(x: float) -> str:
        return costs.inr(round(x))

    lines = [["What is switched on", "Digs per road", "Lane-closure hours", "Trench-hours in rain", "Clashes",
              "Days late", "Cost"]]
    lines += [[LABELS[r.variant], _cell(r.digs_per_road, one), _cell(r.lane_closure_hours, hours),
               _cell(r.trench_hours_in_rain, hours), _cell(r.clashes, one), _cell(r.days_late, one),
               _cell(r.cost_inr, money)] for r in summary.rows]
    widths = [max(len(line[i]) for line in lines) for i in range(len(lines[0]))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(line, widths, strict=True)).rstrip() for line in lines)


def _timing(seconds: dict[str, float], plans: int) -> str:
    parts = " · ".join(f"{v} {seconds[v]:.1f} s" for v in VARIANTS if v != "full")
    total = sum(seconds.values())
    line = f"Planning time: {parts} · total {total:.1f} s for {plans} plans"
    return line + (" Slower than the 3-minute goal." if total > 180 else "")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Plan every test case in the five ways of the Impact page.")
    parser.add_argument("--seeds", default="1-50", help="test cases, for example 1-50 or 1-3,7")
    parser.add_argument("--out", default="evals/results/summary.json")
    parser.add_argument("--csv", default="evals/results/runs.csv")
    parser.add_argument("--fixed-time", action="store_true", help="set generated_at to a fixed time")
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # ₹ and – are not in the Windows pipe code page

    parts = load_parts()
    print(f"Stand-ins: {', '.join(parts.stand_ins)} (their modules are not merged yet)" if parts.stand_ins
          else "Stand-ins: none")
    ev = asyncio.run(evaluate(seeds, parts))
    fake = fake_repairs.count_caught(fake_repairs.load_decide())
    summary = summarize(ev, seeds, fake, fakes.now() if args.fixed_time else datetime.now(UTC))
    write_summary(summary, Path(args.out))
    write_csv(ev.csv_rows, Path(args.csv))

    print(table(summary))
    print(f"Fake repairs caught: {fake.caught} of {fake.total} "
          f"(genuine repairs passed: {fake.genuine_passed} of {fake.genuine_total})" + (f" {fake.note}" if fake.note else ""))
    print(_timing(ev.seconds, len(seeds) * (len(VARIANTS) - 1)))


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


if __name__ == "__main__":
    main()
