"""The hand-made demo (test case 1): real Surathkal roads, 16 works, one procession.

    python -m data.demo                 print the scenario as JSON
    python -m data.demo --out PATH      write the same JSON to PATH (UTF-8)
    python -m data.demo --check         print the demo roads, shared trenches and old-way facts
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date

from contracts import costs, fakes, rules
from contracts.models import (
    Assignment,
    Dept,
    Mode,
    Plan,
    PlanVariant,
    RiskKind,
    RiskWindow,
    Scenario,
    Segment,
    Work,
)
from data.groups import find_parallel_groups
from data.segments import load_segments

START = date(2026, 11, 2)

# Road label -> segment ids, in order. None of the demo street names exist in the OpenStreetMap snapshot
# (only "NITK beach Road" and "Sasihitlu Road" do), so most roads were picked by the fallback rules.
DEMO_ROADS: dict[str, list[str]] = {
    # fallback rule: 5 connected segments heading east (inland) from NH66, 1,047 m, none low-lying.
    # OSM ways 1046119861, 332925053, 1104849506 (x2), 1104849507; all unnamed.
    "Munchur Road": ["S-0463", "S-0170", "S-0651", "S-0650", "S-0654"],
    # fallback rule: the unnamed tertiary way 1278396994 that runs along NH66 (0-8 m away). Second segment is J.
    "NH-66 service road": ["S-0755", "S-0756"],
    # fallback rule: J plus the next segment of "Sasihitlu Road" (OSM way 1256456213), the road that joins at J.
    "Krishnapura cross road": ["S-0756", "S-0730"],
    # fallback rule: one residential segment (OSM way 1050827555, unnamed) next to the service road.
    "Idya lane": ["S-0524"],
    # fallback rule: unnamed tertiary way 219811082 in the north-west, far from every other demo road.
    "Hosabettu cross road": ["S-0099"],
    # fallback rule: unnamed residential way 626812975 in the north-east.
    "Chokkabettu lane": ["S-0279"],
    # real name: OSM way 1046567468 "NITK beach Road". Protected.
    "NITK Beach Road": ["S-0476", "S-0477"],
    # fallback rule: "Sasihitlu Road" (OSM way 1256456213), the northernmost secondary segment. Protected.
    "Hosabettu Road": ["S-0735"],
    # fallback rule: unnamed residential way 548937829 in the south-east.
    "Srinivasnagar road": ["S-0245", "S-0246"],
    # fallback rule: unnamed residential way 1054406158 in the east.
    "Katipalla road": ["S-0612"],
    # fallback rule: unnamed secondary way 219225823 in the east.
    "Kana road": ["S-0092", "S-0093"],
    # fallback rule: unnamed tertiary way 1104849507 in the south.
    "Surathkal market road": ["S-0652"],
    # fallback rule: unnamed tertiary way 1213564154 in the south.
    "Kulai road": ["S-0712"],
}

PROTECTED_ROADS = {
    "Hosabettu Road": (date(2029, 3, 3), "Resurfaced on 3 Mar 2026"),
    "NITK Beach Road": (date(2028, 1, 14), "Concreted on 14 Jan 2025"),
}

# demo story: these flags hold even if the elevation snapshot disagrees
FORCE_LOW_LYING = {
    "NH-66 service road": True,
    "Krishnapura cross road": True,
    "Idya lane": True,
    "Munchur Road": False,
}


def city_segments() -> list[Segment]:
    """All city segments with the demo's protected roads and low-lying flags applied. Fresh copies."""
    segments = load_segments()
    by_id = {s.segment_id: s for s in segments}
    for road, (until, _reason) in PROTECTED_ROADS.items():
        for sid in DEMO_ROADS[road]:
            by_id[sid].protected_until = until
    for road, flag in FORCE_LOW_LYING.items():
        for sid in DEMO_ROADS[road]:
            by_id[sid].low_lying = flag
    return segments


def _munchur(first: int, last: int) -> list[str]:
    return DEMO_ROADS["Munchur Road"][first - 1 : last]


# id, dept, title, road, metres, requested day, days, first mode, second mode, segments, other fields
_TABLE = [
    ("W-104", Dept.water, "Water main", "Munchur Road", 620, 7, 6, "oc", None, _munchur(1, 3),
     {"latest_end": 15, "priority": 4}),
    ("T-221", Dept.telecom, "Fibre duct", "Munchur Road", 620, 10, 4, "oc", "tl", _munchur(1, 3),
     {"earliest_start": 8}),
    ("G-310", Dept.gas, "Gas line", "Munchur Road east", 480, 8, 5, "oc", "tl", _munchur(3, 5), {}),
    ("R-501", Dept.roads, "Resurfacing", "Munchur Road", 1100, 9, 4, "oc", None, _munchur(1, 5),
     {"depends_on": ["W-104", "T-221", "G-310"]}),
    ("D-412", Dept.drainage, "Storm-water drain", "NH-66 service road", 300, 11, 4, "oc", None,
     DEMO_ROADS["NH-66 service road"], {"priority": 4}),
    ("P-118", Dept.power, "Cable shifting", "Krishnapura cross road", 210, 11, 3, "oc", "tl",
     DEMO_ROADS["Krishnapura cross road"], {}),
    ("W-118", Dept.water, "Service line", "Idya lane", 90, 12, 2, "oc", None, DEMO_ROADS["Idya lane"], {}),
    ("T-230", Dept.telecom, "Fibre to tower", "Hosabettu cross road", 350, 7, 3, "tl", "oc",
     DEMO_ROADS["Hosabettu cross road"], {}),
    ("D-415", Dept.drainage, "Drain repair", "Chokkabettu lane", 140, 0, 4, "oc", None,
     DEMO_ROADS["Chokkabettu lane"], {"done": True}),
    ("P-120", Dept.power, "Streetlight cable", "NITK Beach Road", 400, 14, 3, "oc", "tl",
     DEMO_ROADS["NITK Beach Road"], {"priority": 2}),
    ("G-305", Dept.gas, "Service connections", "Hosabettu Road", 260, 5, 3, "oc", "tl",
     DEMO_ROADS["Hosabettu Road"], {}),
    ("W-109", Dept.water, "Valve replacement", "Srinivasnagar road", 120, 3, 2, "oc", None,
     DEMO_ROADS["Srinivasnagar road"], {}),
    ("D-420", Dept.drainage, "Culvert cleaning", "Katipalla road", 180, 16, 3, "oc", None,
     DEMO_ROADS["Katipalla road"], {}),
    ("T-240", Dept.telecom, "Fibre duct", "Kana road", 500, 15, 4, "oc", "tl", DEMO_ROADS["Kana road"], {}),
    ("R-505", Dept.roads, "Pothole patching", "Surathkal market road", 300, 20, 2, "oc", None,
     DEMO_ROADS["Surathkal market road"], {"priority": 2}),
    ("P-125", Dept.power, "Transformer cable", "Kulai road", 150, 6, 2, "oc", "tl", DEMO_ROADS["Kulai road"], {}),
]


def _build_work(row: tuple) -> Work:
    wid, dept, title, road, metres, day, days, first, second, segment_ids, other = row
    first_mode = Mode.open_cut if first == "oc" else Mode.trenchless

    def option(mode: Mode, duration: int):
        return costs.mode_option(dept, float(metres), mode, duration, 1 if mode == Mode.open_cut else 0)

    modes = [option(first_mode, days)]
    if second:  # trenchless takes one day more than open cut
        if first_mode == Mode.open_cut:
            modes.append(option(Mode.trenchless, days + 1))
        else:
            modes.append(option(Mode.open_cut, days - 1))
    fields = {
        "earliest_start": day,
        "latest_end": 27,
        "priority": 3,
        "depends_on": [],
        "done": False,
        **other,
    }
    return Work(
        work_id=wid,
        dept=dept,
        title=title,
        road_name=road,
        segment_ids=list(segment_ids),
        length_m=float(metres),
        requested_start=day,
        modes=modes,
        deposit_inr=costs.deposit_inr(dept, float(metres), first_mode),
        **fields,
    )


def demo_works() -> list[Work]:
    return [_build_work(row) for row in _TABLE]


def demo_scenario() -> Scenario:
    segments = city_segments()
    works = demo_works()
    procession = RiskWindow(
        window_id="EV-DEMO",
        kind=RiskKind.event,
        start_day=18,
        end_day=18,
        segment_ids=DEMO_ROADS["NH-66 service road"] + DEMO_ROADS["Idya lane"],
        value=0.0,
        source="event",
        label="Procession, 20 Nov",
    )
    return Scenario(
        seed=1,
        city="Surathkal",
        start_date=START,
        horizon_days=28,
        segments=segments,
        works=works,
        risk_windows=[procession],
        parallel_groups=find_parallel_groups(works, segments),
    )


def _old_way_plan(scenario: Scenario) -> Plan:
    assignments = []
    for work in scenario.works:
        if work.done:
            continue
        option = work.modes[0]
        assignments.append(
            Assignment(
                work_id=work.work_id,
                start_day=work.requested_start,
                end_day=work.requested_start + option.duration_days - 1,
                mode=option.mode,
                reason="As the department asked.",
            )
        )
    return Plan(
        plan_id=f"P-OLD-{scenario.seed}",
        seed=scenario.seed,
        variant=PlanVariant.naive,
        created_at=fakes.now(),
        assignments=assignments,
    )


def check() -> None:
    scenario = demo_scenario()
    by_id = {s.segment_id: s for s in scenario.segments}
    print("Demo roads")
    for road, ids in DEMO_ROADS.items():
        segs = [by_id[i] for i in ids]
        metres = round(sum(s.length_m for s in segs))
        low = "yes" if all(s.low_lying for s in segs) else "no"
        until = max((s.protected_until for s in segs if s.protected_until), default=None)
        print(f"  {road}: {', '.join(ids)} | {metres} m | low-lying {low} | protected until {until or '-'}")
    print("Shared trenches")
    for g in scenario.parallel_groups:
        print(f"  {g.group_id}: {' + '.join(g.work_ids)} on {', '.join(g.segment_ids)}, saves {costs.inr(g.saving_inr)}")
    plan = _old_way_plan(scenario)
    clashes = rules.find_clashes(scenario, plan, include_risk=False)
    kinds = Counter(c.kind.value for c in clashes)
    print("Old way (every work starts when asked)")
    print(f"  clashes: {len(clashes)} ({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))})")
    digs = rules.digs_per_segment(scenario, plan)
    worst = max(digs.get(s, 0) for s in DEMO_ROADS["Munchur Road"])
    print(f"  most digs on one Munchur segment: {worst}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="The hand-made demo scenario (test case 1)")
    parser.add_argument("--out", help="write the scenario JSON to this file")
    parser.add_argument("--check", action="store_true", help="print the demo roads and old-way facts")
    args = parser.parse_args()
    if args.check:
        check()
        return
    text = demo_scenario().model_dump_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
