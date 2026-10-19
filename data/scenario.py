"""Test cases 1 to 50: the hand-made demo and 49 generated ones."""

from __future__ import annotations

import random

from contracts import costs, fakes, rules
from contracts.models import Assignment, Dept, Mode, Plan, PlanVariant, Scenario, Segment, Work
from data.demo import START, city_segments, demo_scenario
from data.groups import find_parallel_groups

LETTER = {
    Dept.water: "W",
    Dept.drainage: "D",
    Dept.gas: "G",
    Dept.power: "P",
    Dept.telecom: "T",
    Dept.roads: "R",
}
DAYS = {
    Dept.water: (3, 6),
    Dept.drainage: (3, 5),
    Dept.gas: (3, 5),
    Dept.power: (2, 4),
    Dept.telecom: (2, 4),
    Dept.roads: (2, 4),
}
TITLES = {
    Dept.water: ["Water main", "Service line", "Valve replacement", "Pipe repair"],
    Dept.drainage: ["Storm-water drain", "Drain repair", "Culvert cleaning"],
    Dept.gas: ["Gas line", "Service connections"],
    Dept.power: ["Cable shifting", "Streetlight cable", "Transformer cable"],
    Dept.telecom: ["Fibre duct", "Fibre to tower"],
    Dept.roads: ["Resurfacing", "Pothole patching"],
}
TRENCHLESS = {Dept.telecom, Dept.power, Dept.gas}
MAX_ATTEMPTS = 20


class _Retry(Exception):
    """This random draw cannot make the built-in clashes; draw again."""


def _chain(rng: random.Random, allowed: dict[str, Segment], size: int, start: str | None = None) -> list[str]:
    """Up to `size` connected segments: a random allowed start, then random unvisited allowed neighbours."""
    first = start or rng.choice(sorted(allowed))
    path = [first]
    while len(path) < size:
        options = sorted(n for n in allowed[path[-1]].neighbors if n in allowed and n not in path)
        if not options:
            break
        path.append(rng.choice(options))
    return path


def _work(rng: random.Random, allowed: dict[str, Segment], index: int, dept: Dept, segment_ids: list[str],
          start: int, days: int, depends_on: list[str] | None = None) -> Work:
    length = round(sum(allowed[i].length_m for i in segment_ids))
    modes = [costs.mode_option(dept, float(length), Mode.open_cut, days, 1)]
    if dept in TRENCHLESS:
        modes.append(costs.mode_option(dept, float(length), Mode.trenchless, days + 1, 0))
    return Work(
        work_id=f"{LETTER[dept]}-{100 + index}",
        dept=dept,
        title=rng.choice(TITLES[dept]),
        road_name=allowed[segment_ids[0]].name or "Local road",
        segment_ids=segment_ids,
        length_m=float(length),
        requested_start=start,
        earliest_start=start,
        latest_end=27,
        modes=modes,
        priority=rng.randint(2, 4),
        depends_on=depends_on or [],
        deposit_inr=costs.deposit_inr(dept, float(length), Mode.open_cut),
    )


def _build(seed: int, rng: random.Random, segments: list[Segment]) -> list[Work]:
    allowed = {s.segment_id: s for s in segments if not s.protected_until}
    n = rng.randint(14, 20)
    depts = [Dept.water, Dept.telecom, Dept.roads, Dept.gas, Dept.power, Dept.drainage]
    depts += [rng.choice(list(Dept)) for _ in range(n - len(depts))]
    days = [rng.randint(*DAYS[d]) for d in depts]
    works: list[Work] = []

    # works 0 and 1: water and telecom on the same 3-segment chain, starting at most 2 days apart
    chain = _chain(rng, allowed, 3)
    if len(chain) < 3:
        raise _Retry
    s0 = rng.randint(0, 12)
    s1 = s0 + rng.randint(0, 2)
    works.append(_work(rng, allowed, 0, depts[0], chain, s0, days[0]))
    works.append(_work(rng, allowed, 1, depts[1], chain, s1, days[1]))

    # work 2: roads on that chain (plus at most one more segment), starting while both are digging
    low = max(s0, s1)
    high = min(s0 + days[0] - 1, s1 + days[1] - 1)
    road_chain = list(chain)
    extra = sorted(n for n in allowed[chain[-1]].neighbors if n in allowed and n not in chain)
    if extra and rng.random() < 0.5:
        road_chain.append(rng.choice(extra))
    s2 = rng.randint(low, high)
    works.append(_work(rng, allowed, 2, depts[2], road_chain, s2, days[2], [works[0].work_id, works[1].work_id]))

    # work 3: gas on 2 segments that share exactly one segment with work 0 and overlap its days
    options = [(c, m) for c in chain for m in sorted(allowed[c].neighbors) if m in allowed and m not in chain]
    if not options:
        raise _Retry
    shared, other = rng.choice(options)
    first = max(0, s0 - days[3] + 1)
    last = min(works[0].requested_start + days[0] - 1, 27 - days[3] - 3)
    if first > last:
        raise _Retry
    works.append(_work(rng, allowed, 3, depts[3], [shared, other], rng.randint(first, last), days[3]))

    for i in range(4, n):
        ids = _chain(rng, allowed, rng.randint(1, 4))
        start = rng.randint(0, 27 - days[i] - 3)
        works.append(_work(rng, allowed, i, depts[i], ids, start, days[i]))
    return works


def _old_way(scenario: Scenario) -> Plan:
    assignments = []
    for w in scenario.works:
        if w.done:
            continue
        option = w.modes[0]
        assignments.append(Assignment(
            work_id=w.work_id, start_day=w.requested_start, end_day=w.requested_start + option.duration_days - 1,
            mode=option.mode, reason="As the department asked."))
    return Plan(plan_id=f"P-OLD-{scenario.seed}", seed=scenario.seed, variant=PlanVariant.naive,
                created_at=fakes.now(), assignments=assignments)


def generate_scenario(seed: int) -> Scenario:
    if seed == 1:
        return demo_scenario()
    segments = city_segments()
    for attempt in range(MAX_ATTEMPTS):
        rng = random.Random(seed if attempt == 0 else seed * 1000 + attempt)
        try:
            works = _build(seed, rng, segments)
        except _Retry:
            continue
        scenario = Scenario(
            seed=seed,
            city="Surathkal",
            start_date=START,
            horizon_days=28,
            segments=segments,
            works=works,
            risk_windows=[],
            parallel_groups=find_parallel_groups(works, segments),
        )
        if scenario.parallel_groups and rules.clash_count(scenario, _old_way(scenario)) >= 3:
            return scenario
    raise ValueError(f"cannot build test case {seed}")
