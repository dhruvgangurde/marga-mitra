"""Shared clash and dig counting. The metrics (Track 2) and the conflict finder (Track 3) both call these, so their numbers agree."""
from __future__ import annotations

from datetime import timedelta
from itertools import combinations

from contracts.models import Conflict, ConflictKind, Dept, Mode, Plan, RiskKind, Scenario


def _overlap(a0: int, a1: int, b0: int, b1: int) -> tuple[int, int] | None:
    s, e = max(a0, b0), min(a1, b1)
    return (s, e) if s <= e else None


def find_clashes(scenario: Scenario, plan: Plan, include_risk: bool = True) -> list[Conflict]:
    """Every clash in a plan. Callers put the current risk windows into scenario.risk_windows first."""
    works = {w.work_id: w for w in scenario.works}
    segs = {s.segment_id: s for s in scenario.segments}
    live = sorted((a for a in plan.assignments if a.work_id in works and not works[a.work_id].done), key=lambda a: a.work_id)
    out: list[Conflict] = []

    def add(kind: ConflictKind, ids: list[str], seg_ids: set[str], s: int, e: int, note: str) -> None:
        out.append(Conflict(conflict_id=f"C{len(out) + 1}", kind=kind, work_ids=sorted(ids), segment_ids=sorted(seg_ids),
                            start_day=s, end_day=e, note=note))

    for a, b in combinations(live, 2):
        wa, wb = works[a.work_id], works[b.work_id]
        shared = set(wa.segment_ids) & set(wb.segment_ids)
        if not shared or (a.shared_group and a.shared_group == b.shared_group):
            continue
        if (wa.dept == Dept.roads) != (wb.dept == Dept.roads):  # resurfacing vs a utility dig
            r, u = (a, b) if wa.dept == Dept.roads else (b, a)
            if u.mode == Mode.open_cut and u.end_day >= r.start_day:
                add(ConflictKind.order, [r.work_id, u.work_id], shared, r.start_day, max(r.end_day, u.end_day),
                    f"{u.work_id} digs {works[u.work_id].road_name} during or after resurfacing {r.work_id}.")
            continue
        if a.mode == Mode.open_cut and b.mode == Mode.open_cut:
            ov = _overlap(a.start_day, a.end_day, b.start_day, b.end_day)
            if ov:
                add(ConflictKind.same_road, [a.work_id, b.work_id], shared, ov[0], ov[1],
                    f"{a.work_id} and {b.work_id} dig {wa.road_name} on the same days.")

    for a in live:
        w = works[a.work_id]
        if a.mode != Mode.open_cut or w.is_emergency:
            continue
        day = scenario.start_date + timedelta(days=a.start_day)
        protected = {s for s in w.segment_ids if segs[s].protected_until and segs[s].protected_until >= day}
        if protected:
            add(ConflictKind.protected_road, [a.work_id], protected, a.start_day, a.end_day,
                f"{a.work_id} cuts a protected road.")

    if include_risk:
        for win in scenario.risk_windows:
            if win.kind == RiskKind.air:
                continue  # poor air is a dust cost, not a clash
            for a in live:
                w = works[a.work_id]
                if win.kind == RiskKind.rain and a.mode != Mode.open_cut:
                    continue
                hit = set(w.segment_ids) & set(win.segment_ids)
                ov = _overlap(a.start_day, a.end_day, win.start_day, win.end_day)
                if hit and ov:
                    add(ConflictKind.risk, [a.work_id], hit, ov[0], ov[1], f"{a.work_id} is open during {win.label}.")
    return out


def clash_count(scenario: Scenario, plan: Plan) -> int:
    return sum(1 for c in find_clashes(scenario, plan, include_risk=False))


def digs_per_segment(scenario: Scenario, plan: Plan) -> dict[str, int]:
    """How many separate cuts each touched segment gets. A shared trench counts once; trenchless counts zero."""
    works = {w.work_id: w for w in scenario.works}
    cuts: dict[str, set[str]] = {}
    for a in plan.assignments:
        w = works.get(a.work_id)
        if w is None or w.done or a.mode != Mode.open_cut:
            continue
        event = a.shared_group or a.work_id
        for s in w.segment_ids:
            cuts.setdefault(s, set()).add(event)
    return {s: len(e) for s, e in sorted(cuts.items())}


def rain_trench_hours(scenario: Scenario, plan: Plan) -> float:
    """Hours an open trench sits inside a heavy-rain window on its road (24 h per overlapping day, once per work)."""
    works = {w.work_id: w for w in scenario.works}
    hours = 0.0
    for a in plan.assignments:
        w = works.get(a.work_id)
        if w is None or w.done or a.mode != Mode.open_cut:
            continue
        days: set[int] = set()
        for win in scenario.risk_windows:
            if win.kind == RiskKind.rain and set(w.segment_ids) & set(win.segment_ids):
                ov = _overlap(a.start_day, a.end_day, win.start_day, win.end_day)
                if ov:
                    days.update(range(ov[0], ov[1] + 1))
        hours += 24.0 * len(days)
    return hours
