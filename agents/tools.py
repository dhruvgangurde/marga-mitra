"""Date words and the options a department is offered for a clash. Every cost comes from contracts.costs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from string import ascii_uppercase

from contracts import costs
from contracts.models import (
    Assignment,
    Conflict,
    ConflictKind,
    Dept,
    Mode,
    NegotiationOption,
    ParallelGroup,
    Plan,
    RiskKind,
    RiskWindow,
    Scenario,
    Work,
)


def day_label(scenario: Scenario, day: int) -> str:
    d = scenario.start_date + timedelta(days=day)
    return f"{d.day} {d.strftime('%b')}"  # strftime("%-d") fails on Windows


def days_label(scenario: Scenario, start: int, end: int) -> str:
    if start == end:
        return day_label(scenario, start)
    a = scenario.start_date + timedelta(days=start)
    b = scenario.start_date + timedelta(days=end)
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day}–{day_label(scenario, end)}"
    return f"{day_label(scenario, start)} – {day_label(scenario, end)}"


@dataclass
class _Draft:
    words: str
    start: int
    mode: Mode
    duration: int
    members: list[Work]  # every work whose window the option must fit
    group: str | None = None
    share: int = 0
    keep: bool = False


def _assignment(plan: Plan, work_id: str) -> Assignment | None:
    return next((a for a in plan.assignments if a.work_id == work_id), None)


def current_state(plan: Plan, work: Work) -> tuple[int, int, Mode, str | None]:
    """Start, end, mode and trench of a work as the plan has it; the department's own ask when it has no assignment."""
    a = _assignment(plan, work.work_id)
    if a is not None:
        return a.start_day, a.end_day, a.mode, a.shared_group
    first = work.modes[0]
    return work.requested_start, work.requested_start + first.duration_days - 1, first.mode, None


def _offers(work: Work, mode: Mode) -> bool:
    return any(m.mode == mode for m in work.modes)


def _draft(work: Work, words: str, start: int, mode: Mode) -> _Draft | None:
    if not _offers(work, mode):
        return None
    return _Draft(words, start, mode, costs.option_for(work, mode).duration_days, [work])


def _group_saving_share(group: ParallelGroup) -> int:
    return group.saving_inr // len(group.work_ids)


def _same_road(conflict: Conflict, scenario: Scenario, plan: Plan, work: Work, works: dict[str, Work]) -> list[_Draft | None]:
    others = [w for w in conflict.work_ids if w != work.work_id]
    other = works.get(others[0]) if others else None
    if other is None:
        return []
    start, _, mode, group_id = current_state(plan, work)
    out: list[_Draft | None] = []
    group = next((g for g in scenario.parallel_groups if work.work_id in g.work_ids and other.work_id in g.work_ids), None)
    if group is not None:
        members = [works[w] for w in group.work_ids if w in works]
        begin = max(max(m.earliest_start for m in members), min(current_state(plan, m)[0] for m in members))
        if _offers(work, Mode.open_cut):
            length = max(costs.option_for(m, Mode.open_cut).duration_days for m in members if _offers(m, Mode.open_cut))
            out.append(_Draft("Shared trench", begin, Mode.open_cut, length, members, group.group_id,
                              _group_saving_share(group)))
    out.append(_draft(work, "Trenchless", start, Mode.trenchless))
    out.append(_draft(work, f"Move after {other.work_id}", current_state(plan, other)[1] + 1, mode))
    keep = _draft(work, "Keep", start, mode)
    if keep is not None:
        keep.keep = True
        keep.group = group_id
        keep_group = next((g for g in scenario.parallel_groups if g.group_id == group_id), None)
        keep.share = _group_saving_share(keep_group) if keep_group is not None else 0
        out.append(keep)
    return out


def _order(conflict: Conflict, scenario: Scenario, plan: Plan, work: Work, works: dict[str, Work]) -> list[_Draft | None]:
    start, _, mode, _ = current_state(plan, work)
    if work.dept == Dept.roads:
        digs = [w for w in scenario.works
                if not w.done and w.dept != Dept.roads and set(w.segment_ids) & set(work.segment_ids)
                and current_state(plan, w)[2] == Mode.open_cut]
        if not digs:
            return []
        return [_draft(work, "Resurface after every dig", 1 + max(current_state(plan, w)[1] for w in digs), Mode.open_cut)]
    roads = next((works[w] for w in conflict.work_ids if w in works and works[w].dept == Dept.roads), None)
    if roads is None or not _offers(work, mode):
        return []
    before = _draft(work, "Finish before resurfacing", current_state(plan, roads)[0] - costs.option_for(work, mode).duration_days, mode)
    return [before, _draft(work, "Trenchless", start, Mode.trenchless)]


def _protected(conflict: Conflict, scenario: Scenario, plan: Plan, work: Work, works: dict[str, Work]) -> list[_Draft | None]:
    return [_draft(work, "Trenchless", current_state(plan, work)[0], Mode.trenchless)]


def _window_for(conflict: Conflict, scenario: Scenario) -> RiskWindow | None:
    return next((w for w in scenario.risk_windows if w.kind in (RiskKind.rain, RiskKind.event) and w.label in conflict.note),
                None)


def _risk(conflict: Conflict, scenario: Scenario, plan: Plan, work: Work, works: dict[str, Work]) -> list[_Draft | None]:
    window = _window_for(conflict, scenario)
    if window is None:
        return []
    name = window.label.split(",")[0].strip().lower()
    start, _, mode, _ = current_state(plan, work)
    out: list[_Draft | None] = [_draft(work, f"Move after the {name}", window.end_day + 1, mode)]
    if _offers(work, mode):
        out.append(_draft(work, f"Move before the {name}", window.start_day - costs.option_for(work, mode).duration_days, mode))
    if window.kind == RiskKind.rain:
        out.append(_draft(work, "Trenchless", start, Mode.trenchless))
    return out


_BUILDERS = {
    ConflictKind.same_road: _same_road,
    ConflictKind.order: _order,
    ConflictKind.protected_road: _protected,
    ConflictKind.risk: _risk,
}


def _fits(d: _Draft) -> bool:
    last = d.start + d.duration - 1
    return all(d.start >= m.earliest_start and last <= m.latest_end for m in d.members)


def options_for(conflict: Conflict, scenario: Scenario, plan: Plan, work_id: str) -> list[NegotiationOption]:
    works = {w.work_id: w for w in scenario.works}
    work = works.get(work_id)
    if work is None or work_id not in conflict.work_ids:
        return []
    seen: set[tuple[int, Mode, str | None]] = set()
    kept: list[_Draft] = []
    for d in _BUILDERS[conflict.kind](conflict, scenario, plan, work, works):
        if d is None or not _fits(d) or (d.start, d.mode, d.group) in seen:
            continue
        seen.add((d.start, d.mode, d.group))
        kept.append(d)
    out: list[NegotiationOption] = []
    for letter, d in zip(ascii_uppercase, kept, strict=False):
        days = days_label(scenario, d.start, d.start + d.duration - 1)
        label = f"{letter} · Keep {days}" if d.keep else f"{letter} · {d.words}, {days}"
        out.append(NegotiationOption(label=label, work_id=work_id, start_day=d.start, mode=d.mode, shared_group=d.group,
                                     cost_delta_inr=costs.move_cost_inr(work, d.start, d.mode, d.share)))
    return out
