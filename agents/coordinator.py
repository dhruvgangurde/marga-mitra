"""The coordinator: runs the negotiation rounds and turns what the departments agree into scheduler constraints."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from string import ascii_uppercase

from agents import fallback
from agents.conflicts import cluster_conflicts
from agents.department import DEPT_NAMES, DepartmentAgent
from agents.llm import NoLLM
from agents.tools import current_state, day_label, options_for
from contracts import costs
from contracts.interfaces import Emit
from contracts.models import (
    Conflict,
    ConflictKind,
    Dept,
    MessageType,
    Mode,
    NegotiationMessage,
    NegotiationOption,
    NegotiationOutcome,
    Plan,
    RiskKind,
    RiskWindow,
    Scenario,
    SolveConstraints,
    Work,
    WsEvent,
)


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


def make_agent(dept: Dept) -> DepartmentAgent:
    return DepartmentAgent(dept)  # the one place tests swap agents


def _round_timeout() -> float:
    return float(costs.policy()["negotiation"]["round_timeout_s"])


def _max_rounds() -> int:
    return int(costs.policy()["negotiation"]["max_rounds"])


@dataclass
class _Talk:
    """What one negotiate() call has said and decided so far."""
    scenario: Scenario
    plan: Plan
    run_id: str
    emit: Emit
    messages: list[NegotiationMessage] = field(default_factory=list)
    rounds: int = 0
    used_llm: bool = False
    escalated: set[str] = field(default_factory=set)
    pinned_start: dict[str, int] = field(default_factory=dict)
    min_start: dict[str, int] = field(default_factory=dict)
    shared_groups: list[str] = field(default_factory=list)

    def next_id(self) -> str:
        return f"M{len(self.messages) + 1:03d}"

    async def say(self, message: NegotiationMessage) -> None:
        self.messages.append(message)
        await self.emit(WsEvent(type="negotiation.message", data=message.model_dump(mode="json"), ts=datetime.now(UTC)))


def _works_of(cluster: list[Conflict], scenario: Scenario) -> list[Work]:
    ids = {w for c in cluster for w in c.work_ids}
    return [w for w in scenario.works if w.work_id in ids]


def window_of(conflict: Conflict, scenario: Scenario) -> RiskWindow | None:
    """The forecast or event window a risk clash is about (the same rule as the options in agents.tools)."""
    if conflict.kind != ConflictKind.risk:
        return None
    return next((w for w in scenario.risk_windows
                 if w.kind in (RiskKind.rain, RiskKind.event) and w.label in conflict.note), None)


def _only_window(cluster: list[Conflict], scenario: Scenario) -> RiskWindow | None:
    """The one window a cluster is about, when it is made only of risk clashes of that window."""
    windows = {w.window_id: w for c in cluster if (w := window_of(c, scenario)) is not None}
    if len(windows) != 1 or any(c.kind != ConflictKind.risk for c in cluster):
        return None
    return next(iter(windows.values()))


def _merge_forecast_clusters(clusters: list[list[Conflict]], scenario: Scenario) -> list[list[Conflict]]:
    """One forecast reads as one notice: clusters of the same window join the first of them, keeping the order."""
    merged: list[list[Conflict]] = []
    first_at: dict[str, int] = {}
    for cluster in clusters:
        window = _only_window(cluster, scenario)
        if window is None:
            merged.append(cluster)
        elif window.window_id in first_at:
            merged[first_at[window.window_id]] = merged[first_at[window.window_id]] + cluster
        else:
            first_at[window.window_id] = len(merged)
            merged.append(cluster)
    return merged


def _notice_body(cluster: list[Conflict], works: list[Work], scenario: Scenario) -> str:
    ids = listing([w.work_id for w in works])
    window = _only_window(cluster, scenario)
    if window is not None:
        name, _, dates = window.label.partition(",")
        name, dates = name.strip(), dates.strip()
        verb = "is" if len(works) == 1 else "are"
        if window.kind == RiskKind.rain:
            return f"{name} is forecast for {dates}. {ids} {verb} open on low-lying roads then."
        return f"{name} on {dates}. {ids} {verb} on its route."
    roads = " and ".join(dict.fromkeys(w.road_name for w in works))
    between = between_label(scenario, min(c.start_day for c in cluster), max(c.end_day for c in cluster))
    return f"{len(works)} works clash on {roads} between {between}: {ids}."


async def _ask(talk: _Talk, cluster: list[Conflict], work: Work, options: list[NegotiationOption], round_no: int,
               msg_id: str, proposed: int) -> tuple[NegotiationMessage, bool]:
    args = (work_clash(cluster, work.work_id), work.work_id, options, talk.scenario, talk.plan, talk.run_id, round_no,
            msg_id, proposed)
    try:
        return await asyncio.wait_for(make_agent(work.dept).respond(*args), _round_timeout())
    except TimeoutError:
        return await DepartmentAgent(work.dept, NoLLM()).respond(*args)


async def _ask_round(talk: _Talk, cluster: list[Conflict], asked: list[Work], options: dict[str, list[NegotiationOption]],
                     proposals: dict[str, int], round_no: int) -> dict[str, int | None]:
    """Ask the works at the same time, then say their replies in order. Returns each work's chosen option."""
    first = len(talk.messages) + 1
    replies = await asyncio.gather(*(
        _ask(talk, cluster, w, options[w.work_id], round_no, f"M{first + i:03d}", proposals[w.work_id])
        for i, w in enumerate(asked)))
    choice: dict[str, int | None] = {}
    for work, (reply, used) in zip(asked, replies, strict=True):
        await talk.say(reply.model_copy(update={"recipients": ["Coordinator"]}))
        talk.used_llm = talk.used_llm or used
        choice[work.work_id] = reply.chosen_option
    return choice


def _constraints(talk: _Talk, works: list[Work], options: dict[str, list[NegotiationOption]],
                 choice: dict[str, int | None], gone: set[str]) -> None:
    for work in works:
        index = choice[work.work_id]
        if index is None or work.work_id in gone:
            continue
        picked = options[work.work_id][index]
        # shortcut: SolveConstraints has no method field, so an agreed trenchless method is kept as its dates only; the
        # scheduler picks the method by cost and the rules (never open cut on a protected road). Add pinned_mode to the
        # contracts if the demo needs it.
        if picked.shared_group:
            if picked.shared_group not in talk.shared_groups:
                talk.shared_groups.append(picked.shared_group)
        elif picked.start_day > current(talk.plan, work)[0]:
            talk.min_start[work.work_id] = picked.start_day
        else:
            talk.pinned_start[work.work_id] = picked.start_day


def _picked(options: dict[str, list[NegotiationOption]], choice: dict[str, int | None],
            work_id: str) -> NegotiationOption | None:
    index = choice[work_id]
    return None if index is None else options[work_id][index]


def _trench_proposals(talk: _Talk, works: list[Work], options: dict[str, list[NegotiationOption]],
                      choice: dict[str, int | None]) -> dict[str, int]:
    """(a) a work chose a shared trench that another member of it did not choose."""
    out: dict[str, int] = {}
    ids = {w.work_id for w in works}
    for group in talk.scenario.parallel_groups:
        members = [m for m in group.work_ids if m in ids]
        chose = [m for m in members if (o := _picked(options, choice, m)) and o.shared_group == group.group_id]
        if not chose or len(chose) == len(members):
            continue
        for m in members:
            index = choice[m]
            if index is None:
                continue
            if m in chose:
                out.setdefault(m, index)
            else:
                own = next((i for i, o in enumerate(options[m]) if o.shared_group == group.group_id), None)
                out.setdefault(m, fallback.choose(options[m]) if own is None else own)
    return out


def _keep_proposals(talk: _Talk, cluster: list[Conflict], works: list[Work], options: dict[str, list[NegotiationOption]],
                    choice: dict[str, int | None]) -> dict[str, int]:
    """(b) both works of a same-road clash chose to stay put; the one with the lower priority is asked to move."""
    by_id = {w.work_id: w for w in works}
    out: dict[str, int] = {}
    for clash in cluster:
        pair = [by_id[i] for i in clash.work_ids if i in by_id]
        if clash.kind != ConflictKind.same_road or len(pair) != 2:
            continue
        picks = [_picked(options, choice, w.work_id) for w in pair]
        if not all(o is not None and is_keep(o, talk.plan, w) for o, w in zip(picks, pair, strict=True)):
            continue
        # the lower priority moves; on a tie the later request, then the larger id
        mover = max(pair, key=lambda w: (-w.priority, w.requested_start, w.work_id))
        moving = [i for i, o in enumerate(options[mover.work_id]) if not is_keep(o, talk.plan, mover)]
        for w in pair:
            index = choice[w.work_id]
            if w is mover and moving:
                index = moving[fallback.choose([options[w.work_id][i] for i in moving])]
            if index is not None:
                out.setdefault(w.work_id, index)
    return out


def _disagreements(talk: _Talk, cluster: list[Conflict], works: list[Work], options: dict[str, list[NegotiationOption]],
                   choice: dict[str, int | None]) -> dict[str, int]:
    """Works in a contradiction, in scenario order, each with the option the coordinator proposes."""
    found = _trench_proposals(talk, works, options, choice)
    for work_id, index in _keep_proposals(talk, cluster, works, options, choice).items():
        found.setdefault(work_id, index)
    return {w.work_id: found[w.work_id] for w in works if w.work_id in found}


def _round_notice(talk: _Talk, r: int, asked: list[Work], options: dict[str, list[NegotiationOption]],
                  proposals: dict[str, int]) -> NegotiationMessage:
    named = [f"option {options[w.work_id][proposals[w.work_id]].label[0]} for {w.work_id}" for w in asked]
    ids = [w.work_id for w in asked]
    return NegotiationMessage(
        msg_id=talk.next_id(), run_id=talk.run_id, round=r, sender="coordinator",
        recipients=list(dict.fromkeys(DEPT_NAMES[w.dept.value] for w in asked)), type=MessageType.NOTICE, work_ids=ids,
        body=f"Round {r}: {listing(ids)} still disagree. The coordinator proposes {listing(named)}.", ts=datetime.now(UTC))


async def _negotiate_cluster(talk: _Talk, cluster: list[Conflict]) -> None:
    works = _works_of(cluster, talk.scenario)
    options = {w.work_id: work_options(cluster, talk.scenario, talk.plan, w.work_id) for w in works}
    await talk.say(NegotiationMessage(
        msg_id=talk.next_id(), run_id=talk.run_id, round=1, sender="coordinator",
        recipients=list(dict.fromkeys(DEPT_NAMES[w.dept.value] for w in works)), type=MessageType.NOTICE,
        work_ids=[w.work_id for w in works], body=_notice_body(cluster, works, talk.scenario), ts=datetime.now(UTC)))
    proposals = {w.work_id: fallback.choose(options[w.work_id]) for w in works}
    choice = await _ask_round(talk, cluster, works, options, proposals, 1)
    gone = {w for w, i in choice.items() if i is None}  # a work that said ESCALATE is never asked again
    r = 1
    while (open_ := _disagreements(talk, cluster, works, options, choice)) and r < _max_rounds():
        r += 1
        asked = [w for w in works if w.work_id in open_ and w.work_id not in gone]
        await talk.say(_round_notice(talk, r, asked, options, open_))
        choice.update(await _ask_round(talk, cluster, asked, options, open_, r))
        gone |= {w.work_id for w in asked if choice[w.work_id] is None}
    talk.rounds = max(talk.rounds, r)
    gone |= set(_disagreements(talk, cluster, works, options, choice))
    _constraints(talk, works, options, choice, gone)
    if gone:
        talk.escalated |= gone
        ids = [w.work_id for w in works if w.work_id in gone]
        await talk.say(NegotiationMessage(
            msg_id=talk.next_id(), run_id=talk.run_id, round=r, sender="coordinator", recipients=["Scheduler"],
            type=MessageType.ESCALATE, work_ids=ids,
            body=f"The scheduler decides the remaining dates for {listing(ids)}.", ts=datetime.now(UTC)))


async def negotiate(scenario: Scenario, plan: Plan, conflicts: list[Conflict], run_id: str,
                    emit: Emit) -> NegotiationOutcome:
    talk = _Talk(scenario, plan, run_id, emit)
    for cluster in _merge_forecast_clusters(cluster_conflicts(conflicts), scenario):
        await _negotiate_cluster(talk, cluster)
    constraints = SolveConstraints(pinned_start=talk.pinned_start, min_start=talk.min_start,
                                   shared_groups=talk.shared_groups)
    return NegotiationOutcome(run_id=run_id, rounds=talk.rounds, messages=talk.messages, constraints=constraints,
                              escalated=sorted(talk.escalated), used_llm=talk.used_llm)
