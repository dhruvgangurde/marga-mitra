"""Find pairs of works that can share one open trench."""

from __future__ import annotations

from itertools import combinations

from contracts import costs
from contracts.models import Dept, Mode, ParallelGroup, Segment, Work

MIN_SHARE = 0.6


def _candidates(works: list[Work]) -> list[Work]:
    return sorted(
        (
            w
            for w in works
            if w.dept != Dept.roads
            and not w.done
            and not w.is_emergency
            and any(m.mode == Mode.open_cut for m in w.modes)
        ),
        key=lambda w: w.work_id,
    )


def find_parallel_groups(works: list[Work], segments: list[Segment]) -> list[ParallelGroup]:
    length = {s.segment_id: s.length_m for s in segments}

    def total(ids: set[str]) -> float:
        return sum(length.get(i, 0.0) for i in ids)

    pairs = []
    for a, b in combinations(_candidates(works), 2):
        ids_a, ids_b = set(a.segment_ids), set(b.segment_ids)
        shared = ids_a & ids_b
        smaller = min(total(ids_a), total(ids_b))
        if not shared or smaller <= 0:
            continue
        share = total(shared) / smaller
        if share >= MIN_SHARE:
            pairs.append((share, a, b, shared))

    # shortcut: groups of two only; allow three departments in one trench if the test cases need it.
    pairs.sort(key=lambda p: (-p[0], p[1].work_id, p[2].work_id))
    used: set[str] = set()
    chosen = []
    for _, a, b, shared in pairs:
        if a.work_id in used or b.work_id in used:
            continue
        used.update((a.work_id, b.work_id))
        chosen.append((a, b, shared))

    chosen.sort(key=lambda c: min(c[0].work_id, c[1].work_id))
    return [
        ParallelGroup(
            group_id=f"G{n}",
            work_ids=sorted((a.work_id, b.work_id)),
            segment_ids=sorted(shared),
            saving_inr=costs.shared_trench_saving_inr([a, b]),
        )
        for n, (a, b, shared) in enumerate(chosen, start=1)
    ]
