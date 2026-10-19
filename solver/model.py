"""The time-indexed scheduling model: one yes/no choice per work, method and start day."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from ortools.sat.python import cp_model

from contracts import costs
from contracts.models import Dept, Mode, ParallelGroup, Scenario, Segment, SolveConstraints, Work, WorkModeOption

UNPLACED_COST = 100000


def weights() -> dict[str, float]:
    return costs.policy()["objective_weights"]


@dataclass
class Built:
    model: cp_model.CpModel
    choices: dict[tuple[str, Mode, int], tuple[cp_model.IntVar, int]] = field(default_factory=dict)
    trenches: dict[tuple[str, int], tuple[cp_model.IntVar, int]] = field(default_factory=dict)
    placed: dict[str, cp_model.IntVar] = field(default_factory=dict)
    groups: dict[str, ParallelGroup] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def protected_on(scenario: Scenario, work: Work, start: int) -> bool:
    day = scenario.start_date + timedelta(days=start)
    segs = {s.segment_id: s for s in scenario.segments}
    return any(segs[s].protected_until and segs[s].protected_until >= day for s in work.segment_ids)


def allowed(scenario: Scenario, constraints: SolveConstraints, work: Work, option: WorkModeOption, start: int) -> bool:
    end = start + option.duration_days - 1
    if start < work.earliest_start or end > work.latest_end or end > scenario.horizon_days - 1:
        return False
    pinned = constraints.pinned_start.get(work.work_id)
    if pinned is not None and pinned != start:
        return False
    if start < constraints.min_start.get(work.work_id, start):
        return False
    if any(start <= d <= end for d in constraints.forbidden_days.get(work.work_id, [])):
        return False
    if work.is_emergency:
        return start == work.requested_start
    return not (option.mode == Mode.open_cut and protected_on(scenario, work, start))


# The weights turn choices into costs only in the three functions below.
def _own_cost(work: Work, option: WorkModeOption, start: int, w: dict[str, float]) -> int:
    shift = start - work.requested_start
    return option.cost_inr // 1000 + round(2 * w["delay"]) * max(0, shift) + abs(shift)


def _choice_cost(work: Work, option: WorkModeOption, start: int, segments_by_id: dict[str, Segment],
                 w: dict[str, float]) -> int:
    cost = _own_cost(work, option, start, w)
    cost += round(w["disruption"] * costs.lane_closure_hours(work, option.mode, option.duration_days, segments_by_id))
    if option.mode == Mode.open_cut:
        cost += round(100 * w["excavations"])
    return cost


def _trench_cost(members: list[Work], group: ParallelGroup, start: int, duration: int,
                 segments_by_id: dict[str, Segment], w: dict[str, float]) -> int:
    cost = sum(_own_cost(m, costs.option_for(m, Mode.open_cut), start, w) for m in members)
    hours = max(costs.lane_closure_hours(m, Mode.open_cut, duration, segments_by_id) for m in members)
    return cost + round(w["disruption"] * hours) + round(100 * w["excavations"]) - group.saving_inr // 1000


def _trench_starts(scenario: Scenario, constraints: SolveConstraints, members: list[Work]) -> tuple[int, list[int]]:
    """The trench length (the longest member) and every start day that every member allows."""
    if any(m.done or all(o.mode != Mode.open_cut for o in m.modes) for m in members):
        return 0, []
    duration = max(costs.option_for(m, Mode.open_cut).duration_days for m in members)
    options = [costs.option_for(m, Mode.open_cut).model_copy(update={"duration_days": duration}) for m in members]
    starts = [s for s in range(scenario.horizon_days)
              if all(allowed(scenario, constraints, m, o, s) for m, o in zip(members, options, strict=True))]
    return duration, starts


# (choice literal, start, duration, open cut) for every way a work can be placed
Slot = tuple[cp_model.IntVar, int, int, bool]


def _expr(slots: list[Slot], value) -> cp_model.LinearExpr:
    return cp_model.LinearExpr.weighted_sum([s[0] for s in slots], [value(s) for s in slots])


def _add_order(m: cp_model.CpModel, scenario: Scenario, built: Built, slots: dict[str, list[Slot]]) -> None:
    """Resurfacing comes after every utility cut on its road; a work starts after the works it depends on end."""
    planned = {w.work_id: w for w in scenario.works if not w.done}
    # end is exclusive here; every expression is 0 when the work is not placed
    start = {wid: _expr(slots.get(wid, []), lambda x: x[1]) for wid in planned}
    end_open_cut = {wid: _expr(slots.get(wid, []), lambda x: (x[1] + x[2]) if x[3] else 0) for wid in planned}
    end_any = {wid: _expr(slots.get(wid, []), lambda x: x[1] + x[2]) for wid in planned}
    for r in planned.values():
        if r.dept != Dept.roads:
            continue
        for u in planned.values():
            if u.dept != Dept.roads and set(u.segment_ids) & set(r.segment_ids):
                m.add(start[r.work_id] >= end_open_cut[u.work_id]).only_enforce_if(built.placed[r.work_id])
    for w in planned.values():
        for p in w.depends_on:
            if p in planned:
                m.add(start[w.work_id] >= end_any[p]).only_enforce_if(built.placed[w.work_id])


def _accept_groups(scenario: Scenario, constraints: SolveConstraints, built: Built) -> dict[str, tuple[int, list[int]]]:
    """Accepted groups that fit, with their trench length and allowed starts; the others get a note."""
    if not constraints.use_groups:
        return {}
    works = {w.work_id: w for w in scenario.works}
    fits: dict[str, tuple[int, list[int]]] = {}
    taken: set[str] = set()
    for group in scenario.parallel_groups:
        # a work can sit in only one trench, so a later group that reuses a member is skipped
        if group.group_id not in constraints.shared_groups or taken & set(group.work_ids):
            continue
        if not all(wid in works for wid in group.work_ids):
            continue
        duration, starts = _trench_starts(scenario, constraints, [works[wid] for wid in group.work_ids])
        if not starts:
            built.notes.append(f"Shared trench {group.group_id} does not fit the allowed dates, "
                               "so its works are planned one by one.")
            continue
        built.groups[group.group_id] = group
        fits[group.group_id] = (duration, starts)
        taken |= set(group.work_ids)
    return fits


def build(scenario: Scenario, constraints: SolveConstraints) -> Built:
    built = Built(model=cp_model.CpModel())
    m = built.model
    w = weights()
    segments_by_id = {s.segment_id: s for s in scenario.segments}
    works = {wk.work_id: wk for wk in scenario.works}
    lits: list[cp_model.IntVar] = []
    coefs: list[int] = []
    unplaced_const = 0
    slots: dict[str, list[Slot]] = {}
    seg_intervals: dict[str, list[cp_model.IntervalVar]] = {}

    for gid, (duration, starts) in _accept_groups(scenario, constraints, built).items():
        group = built.groups[gid]
        members = [works[wid] for wid in group.work_ids]
        placed = m.new_bool_var(f"placed_{gid}")
        built.placed[gid] = placed
        segs = sorted({s for mem in members for s in mem.segment_ids})
        ts = []
        for start in starts:
            t = m.new_bool_var(f"t_{gid}_{start}")
            built.trenches[(gid, start)] = (t, duration)
            ts.append(t)
            lits.append(t)
            coefs.append(_trench_cost(members, group, start, duration, segments_by_id, w))
            iv = m.new_optional_fixed_size_interval_var(start, duration, t, f"i_{gid}_{start}")
            for s in segs:
                seg_intervals.setdefault(s, []).append(iv)
            for mem in members:
                slots.setdefault(mem.work_id, []).append((t, start, duration, True))
        m.add(cp_model.LinearExpr.sum(ts) == placed)
        for mem in members:
            built.placed[mem.work_id] = placed
            if mem.is_emergency:
                m.add(placed == 1)
        unplaced_const += UNPLACED_COST * len(members)
        lits.append(placed)
        coefs.append(-UNPLACED_COST * len(members))

    in_trench = {wid for g in built.groups.values() for wid in g.work_ids}
    for work in scenario.works:
        if work.done or work.work_id in in_trench:
            continue
        placed = m.new_bool_var(f"placed_{work.work_id}")
        built.placed[work.work_id] = placed
        xs = []
        for option in work.modes:
            for start in range(scenario.horizon_days):
                if not allowed(scenario, constraints, work, option, start):
                    continue
                x = m.new_bool_var(f"x_{work.work_id}_{option.mode.value}_{start}")
                open_cut = option.mode == Mode.open_cut
                built.choices[(work.work_id, option.mode, start)] = (x, option.duration_days)
                slots.setdefault(work.work_id, []).append((x, start, option.duration_days, open_cut))
                xs.append(x)
                lits.append(x)
                coefs.append(_choice_cost(work, option, start, segments_by_id, w))
                if open_cut:
                    iv = m.new_optional_fixed_size_interval_var(start, option.duration_days, x,
                                                                f"i_{work.work_id}_{start}")
                    for s in work.segment_ids:
                        seg_intervals.setdefault(s, []).append(iv)
        m.add(cp_model.LinearExpr.sum(xs) == placed)
        if work.is_emergency:
            m.add(placed == 1)
        # UNPLACED_COST * (1 - placed)
        unplaced_const += UNPLACED_COST
        lits.append(placed)
        coefs.append(-UNPLACED_COST)
    for intervals in seg_intervals.values():
        if len(intervals) > 1:
            m.add_no_overlap(intervals)
    _add_order(m, scenario, built, slots)
    m.minimize(cp_model.LinearExpr.weighted_sum(lits, coefs) + unplaced_const)
    return built
