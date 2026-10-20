"""The demo story on test case 1, checked on the real roads.

    python -m evals.story
"""
from __future__ import annotations

import asyncio
import sys

from contracts import rules
from contracts.models import Assignment, Mode, Plan, RiskKind, Scenario
from evals.run import Parts, eval_windows, force_no_llm, load_parts, risk_plan, with_windows
from solver.baselines import naive_plan
from solver.solve import days_text

MUNCHUR = ("W-104", "T-221", "G-310", "R-501")
RAIN_WORKS = ("D-412", "P-118", "W-118")
RAIN_DAYS = {12, 13}
# the dates in the screen specs: a target for the demo, not a rule
SPEC_DATES = {"W-104": "10–15 Nov", "T-221": "10–15 Nov", "G-310": "16–20 Nov", "R-501": "24–27 Nov",
              "D-412": "16–19 Nov", "P-118": "21–23 Nov", "W-118": "21–22 Nov"}


def _days(a: Assignment) -> set[int]:
    return set(range(a.start_day, a.end_day + 1))


def _by_id(plan: Plan) -> dict[str, Assignment]:
    return {a.work_id: a for a in plan.assignments}


def _plan_facts(a: dict[str, Assignment]) -> dict[str, bool]:
    w, t, g, r = (a[wid] for wid in MUNCHUR)
    return {
        "Water and Telecom share one trench": (w.shared_group is not None and w.shared_group == t.shared_group
                                               and (w.start_day, w.end_day) == (t.start_day, t.end_day)),
        "Gas starts after the trench": g.start_day > max(w.end_day, t.end_day),
        "Resurfacing comes last": r.start_day > max(w.end_day, t.end_day, g.end_day),
        "Protected roads are not cut": a["P-120"].mode == a["G-305"].mode == Mode.trenchless,
    }


def _route_free(scenario: Scenario, a: dict[str, Assignment]) -> bool:
    works = {w.work_id: w for w in scenario.works}
    for event in (win for win in scenario.risk_windows if win.kind == RiskKind.event):
        window = set(range(event.start_day, event.end_day + 1))
        if any(set(works[wid].segment_ids) & set(event.segment_ids) and _days(x) & window for wid, x in a.items()):
            return False
    return True


async def _plans(parts: Parts) -> tuple[Scenario, Plan, Plan, Plan, Scenario]:
    force_no_llm()
    scenario = parts.generate_scenario(1)
    naive = naive_plan(scenario)
    calm_windows = eval_windows(scenario, parts, with_rain=False)
    rain_windows = eval_windows(scenario, parts)
    before = await risk_plan(scenario, parts, naive, calm_windows, "EVAL-STORY-before")
    after = await risk_plan(scenario, parts, naive, rain_windows, "EVAL-STORY-after")
    return scenario, naive, before, after, with_windows(scenario, rain_windows)


def story(parts: Parts) -> tuple[list[tuple[str, bool]], list[tuple[str, str, str, str]]]:
    """The story checks as (name, ok) and the date table as (work, screen specs, before rain, after rain)."""
    scenario, naive, before, after, rainy = asyncio.run(_plans(parts))
    works = {w.work_id: w for w in scenario.works}
    a0, a1 = _by_id(before), _by_id(after)
    munchur = {s for wid in MUNCHUR for s in works[wid].segment_ids}
    digs = rules.digs_per_segment(scenario, naive)
    facts0, facts1 = _plan_facts(a0), _plan_facts(a1)
    checks = [
        ("Old way digs one Munchur segment 4 times", max(digs.get(s, 0) for s in munchur) == 4),
        ("Old way has 9 clashes", rules.clash_count(scenario, naive) == 9),
        *((name, facts0[name] and facts1[name]) for name in facts0),
        ("No trench in the rain", rules.rain_trench_hours(rainy, after) == 0.0),
        ("The rain works moved", all(a1[wid].mode != Mode.open_cut or not _days(a1[wid]) & RAIN_DAYS
                                     for wid in RAIN_WORKS)),
        ("The procession route stays free", _route_free(rainy, a0) and _route_free(rainy, a1)),
    ]
    dates = [(wid, spec, days_text(scenario, a0[wid].start_day, a0[wid].end_day),
              days_text(scenario, a1[wid].start_day, a1[wid].end_day)) for wid, spec in SPEC_DATES.items()]
    return checks, dates


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # – is not in the Windows pipe code page
    parts = load_parts()
    if "data.scenario" in parts.stand_ins:
        print("The demo story needs T4's data on main.")
        sys.exit(1)
    checks, dates = story(parts)
    for name, ok in checks:
        print(f"{'ok    ' if ok else 'NOT OK'}  {name}")
    rows = [("Work", "Screen specs", "Before rain", "After rain"), *dates]
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    print()
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip())


if __name__ == "__main__":
    main()
