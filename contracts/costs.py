"""Deterministic money and disruption numbers. Agents, the scheduler and the UI use these; an LLM never invents a number."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from contracts.models import Dept, Mode, Segment, Work, WorkModeOption

POLICY_PATH = Path(__file__).resolve().parents[1] / "policy" / "policy.yaml"


@lru_cache
def policy() -> dict[str, Any]:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def _rates() -> dict[str, Any]:
    return policy()["costs"]


def _round100(x: float) -> int:
    return int(round(x / 100.0)) * 100


def dig_cost_inr(dept: Dept, length_m: float, mode: Mode) -> int:
    r = _rates()
    base = r["per_metre_inr"][dept.value] * length_m
    return _round100(base * (r["trenchless_factor"] if mode == Mode.trenchless else 1.0))


def restoration_cost_inr(length_m: float, mode: Mode) -> int:
    r = _rates()
    if mode == Mode.trenchless:
        pits = max(2, int(length_m // r["trenchless_pit_every_m"]) + 1)
        return _round100(pits * 2.0 * r["restoration_per_m2_inr"])
    return _round100(length_m * r["trench_width_m"] * r["restoration_per_m2_inr"])


def work_cost_inr(dept: Dept, length_m: float, mode: Mode) -> int:
    return dig_cost_inr(dept, length_m, mode) + restoration_cost_inr(length_m, mode)


def deposit_inr(dept: Dept, length_m: float, mode: Mode) -> int:
    """Deposit held until the repair is verified, rounded to the nearest ₹10,000 (at least ₹10,000)."""
    raw = work_cost_inr(dept, length_m, mode) * _rates()["deposit_share"]
    return max(10000, int(round(raw / 10000.0)) * 10000)


def mode_option(dept: Dept, length_m: float, mode: Mode, duration_days: int, lanes_closed: int) -> WorkModeOption:
    dust = 0.0 if mode == Mode.trenchless else 0.6
    return WorkModeOption(mode=mode, duration_days=duration_days, cost_inr=work_cost_inr(dept, length_m, mode),
                          lanes_closed=lanes_closed, dust=dust)


def shared_trench_saving_inr(works: list[Work]) -> int:
    """One open trench for all works: every work but the longest saves its restoration and its excavation share."""
    if len(works) < 2:
        return 0
    r = _rates()
    ordered = sorted(works, key=lambda w: w.length_m, reverse=True)
    saving = 0.0
    for w in ordered[1:]:
        saving += restoration_cost_inr(w.length_m, Mode.open_cut)
        saving += r["excavation_share"] * dig_cost_inr(w.dept, w.length_m, Mode.open_cut)
    return _round100(saving)


def delay_cost_inr(days_late: int) -> int:
    return max(0, days_late) * _rates()["delay_per_day_inr"]


def option_for(work: Work, mode: Mode) -> WorkModeOption:
    for m in work.modes:
        if m.mode == mode:
            return m
    raise ValueError(f"{work.work_id} has no {mode.value} option")


def lane_closure_hours(work: Work, mode: Mode, days: int, segments: dict[str, Segment]) -> float:
    """Lanes shut x how busy the road is x working hours x days."""
    weight = max(segments[s].traffic_weight for s in work.segment_ids)
    return option_for(work, mode).lanes_closed * weight * _rates()["working_hours_per_day"] * days


def move_cost_inr(work: Work, new_start: int, new_mode: Mode, shared_saving_inr: int = 0) -> int:
    """Cost change of moving a work against what its department asked for (positive = more expensive)."""
    default = work.modes[0]
    late = max(0, new_start - work.requested_start)
    return option_for(work, new_mode).cost_inr - default.cost_inr + delay_cost_inr(late) - shared_saving_inr


def inr(amount: int) -> str:
    """₹ with Indian digit grouping: 240000 -> '₹2,40,000'."""
    sign = "−" if amount < 0 else ""
    s = str(abs(int(amount)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return f"{sign}₹{s}"
