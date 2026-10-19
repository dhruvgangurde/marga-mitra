"""The clash list and the clusters the coordinator sends one notice for."""
from __future__ import annotations

from contracts import rules
from contracts.models import Conflict, Plan, Scenario


def detect_conflicts(scenario: Scenario, plan: Plan) -> list[Conflict]:
    # no rules of its own: the metrics call the same function, so the counts always agree
    return rules.find_clashes(scenario, plan)


def cluster_conflicts(conflicts: list[Conflict]) -> list[list[Conflict]]:
    """Clashes that share a work or a segment, directly or through others, form one cluster."""
    parent = list(range(len(conflicts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first_seen: dict[str, int] = {}
    for i, c in enumerate(conflicts):
        for key in [*(f"w:{w}" for w in c.work_ids), *(f"s:{s}" for s in c.segment_ids)]:
            j = first_seen.setdefault(key, i)
            parent[find(i)] = find(j)

    groups: dict[int, list[Conflict]] = {}
    for i, c in enumerate(conflicts):
        groups.setdefault(find(i), []).append(c)
    # dicts keep insertion order, so clusters follow their first clash in the input
    return list(groups.values())
