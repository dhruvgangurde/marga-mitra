"""The coordinator: runs the negotiation rounds and turns what the departments agree into scheduler constraints."""
from __future__ import annotations

from datetime import timedelta
from string import ascii_uppercase

from agents.tools import current_state, day_label, options_for
from contracts.models import Conflict, Mode, NegotiationOption, Plan, Scenario, Work


def work_options(cluster: list[Conflict], scenario: Scenario, plan: Plan, work_id: str) -> list[NegotiationOption]:
    """Every option a work is offered across the clashes of its cluster, without repeats, lettered A, B, C…"""
    joined: list[NegotiationOption] = []
    seen: set[tuple[int, Mode, str | None]] = set()
    for clash in cluster:
        if work_id not in clash.work_ids:
            continue
        for o in options_for(clash, scenario, plan, work_id):
            key = (o.start_day, o.mode, o.shared_group)
            if key not in seen:
                seen.add(key)
                joined.append(o)
    return [o.model_copy(update={"label": f"{letter} · {o.label.split(' · ', 1)[1]}"})
            for letter, o in zip(ascii_uppercase, joined, strict=False)]


def work_clash(cluster: list[Conflict], work_id: str) -> Conflict:
    """The first clash naming the work, with the notes of all its clashes, which is what the department reads."""
    mine = [c for c in cluster if work_id in c.work_ids]
    return mine[0].model_copy(update={"note": " ".join(c.note for c in mine)})


def current(plan: Plan, work: Work) -> tuple[int, Mode]:
    start, _, mode, _ = current_state(plan, work)
    return start, mode


def is_keep(option: NegotiationOption, plan: Plan, work: Work) -> bool:
    """The option leaves the work where it is, trench included: Phase 1's Keep copies the work's current trench id."""
    start, _, mode, group = current_state(plan, work)
    return (option.start_day, option.mode, option.shared_group) == (start, mode, group)


def listing(ids: list[str]) -> str:
    if len(ids) < 2:
        return "".join(ids)
    return f"{', '.join(ids[:-1])} and {ids[-1]}"


def between_label(scenario: Scenario, a: int, b: int) -> str:
    first = scenario.start_date + timedelta(days=a)
    last = scenario.start_date + timedelta(days=b)
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day} and {day_label(scenario, b)}"
    return f"{day_label(scenario, a)} and {day_label(scenario, b)}"
