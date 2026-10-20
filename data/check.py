"""Demo check: can the demo story still happen on the real roads?

    python -m data.check
"""

from __future__ import annotations

import sys
from collections import Counter

from contracts import costs, rules
from contracts.models import Dept, Mode, Scenario, Work
from data.demo import _TABLE, DEMO_ROADS, PROTECTED_ROADS, demo_scenario
from data.elevation import ELEVATIONS
from data.osm_import import SNAPSHOT
from data.scenario import _old_way

Line = tuple[str, str]  # status "PASS", "WARN" or "FAIL", and one plain sentence


def show(lines: list[Line]) -> None:
    for status, text in lines:
        print(f"{status:<4} {text}")


def road_lines(scenario: Scenario) -> list[Line]:
    by_id = {s.segment_id: s for s in scenario.segments}
    lines: list[Line] = []

    # 1. snapshots
    missing = []
    if not SNAPSHOT.exists():
        missing.append("python -m data.osm_import --fetch")
    if not ELEVATIONS.exists():
        missing.append("python -m data.elevation --fetch")
    if missing:
        lines.append(("FAIL", "A road snapshot is missing: run " + " and ".join(missing) + "."))
    else:
        lines.append(("PASS", f"Both road snapshots exist ({SNAPSHOT.name} and {ELEVATIONS.name})."))

    # 2. Munchur Road
    ids = DEMO_ROADS["Munchur Road"]
    segs = [by_id[i] for i in ids if i in by_id]
    metres = round(sum(s.length_m for s in segs))
    problems = []
    if len(segs) != 5:
        problems.append(f"it has {len(segs)} segments, not 5")
    for a, b in zip(ids, ids[1:], strict=False):
        if a in by_id and b not in by_id[a].neighbors:
            problems.append(f"{a} and {b} are not neighbours")
    if not 900 <= metres <= 1400:
        problems.append(f"it is {metres:,} m long, not 900 to 1,400 m")
    problems += [f"segment {s.segment_id} is low-lying" for s in segs if s.low_lying]
    if problems:
        lines.append(("FAIL", "Munchur Road: " + "; ".join(problems) + "."))
    else:
        lines.append(("PASS", f"Munchur Road has 5 connected segments, {metres:,} m in total, none low-lying."))

    # 3. low-lying roads
    low_roads = ["NH-66 service road", "Krishnapura cross road", "Idya lane"]
    dry = [i for r in low_roads for i in DEMO_ROADS[r] if not by_id[i].low_lying]
    if dry:
        lines.append(("FAIL", "These segments should be low-lying but are not: " + ", ".join(dry) + "."))
    else:
        count = len({i for r in low_roads for i in DEMO_ROADS[r]})
        lines.append(("PASS", f"All {count} segments of NH-66 service road, Krishnapura cross road and Idya lane are low-lying."))

    # 4. the junction
    nh, kr, idya = (set(DEMO_ROADS[r]) for r in low_roads)
    junction = sorted(nh & kr)
    if len(junction) == 1 and not idya & (nh | kr):
        lines.append(("PASS", f"NH-66 service road and Krishnapura cross road share one segment ({junction[0]}); Idya lane shares none."))
    else:
        lines.append(("FAIL", f"The two roads share {len(junction)} segments and Idya lane shares {len(idya & (nh | kr))}; expected 1 and 0."))

    # 5. protected roads
    problems = []
    for road, (until, _reason) in PROTECTED_ROADS.items():
        for sid in DEMO_ROADS[road]:
            if by_id[sid].protected_until != until:
                problems.append(f"{sid} on {road} is not protected until {until}")
    protected = {s.segment_id for s in scenario.segments if s.protected_until}
    on_protected = sorted(w.work_id for w in scenario.works if set(w.segment_ids) & protected)
    if on_protected != ["G-305", "P-120"]:
        problems.append("the works on protected segments are " + ", ".join(on_protected) + ", not G-305 and P-120")
    for w in scenario.works:
        if w.work_id in ("P-120", "G-305") and not any(m.mode == Mode.trenchless for m in w.modes):
            problems.append(f"{w.work_id} does not offer trenchless")
    if problems:
        lines.append(("FAIL", "Protected roads: " + "; ".join(problems) + "."))
    else:
        lines.append(("PASS", "Hosabettu Road and NITK Beach Road are protected; only P-120 and G-305 are on them, and both offer trenchless."))

    # 6. the 16 works
    problems = []
    expected = [row[0] for row in _TABLE]
    if [w.work_id for w in scenario.works] != expected:
        problems.append("the works are not the 16 in the table, in order")
    for w in scenario.works:
        gone = [i for i in w.segment_ids if i not in by_id]
        if gone:
            problems.append(f"{w.work_id} uses unknown segments {', '.join(gone)}")
            continue
        covered = sum(by_id[i].length_m for i in w.segment_ids)
        if covered < 0.75 * w.length_m:
            problems.append(f"{w.work_id} covers {covered:.0f} m of {w.length_m:.0f} m")
        want = costs.deposit_inr(w.dept, w.length_m, w.modes[0].mode)
        if w.deposit_inr != want:
            problems.append(f"{w.work_id} has deposit {w.deposit_inr}, expected {want}")
    depts = {w.dept for w in scenario.works}
    if depts != set(Dept):
        problems.append("these departments are missing: " + ", ".join(sorted(d.value for d in set(Dept) - depts)))
    if problems:
        lines.append(("FAIL", "Works: " + "; ".join(problems) + "."))
    else:
        lines.append(("PASS", f"{len(scenario.works)} works in table order, all segments exist, each covers at least 75% of its length, deposits match, all {len(depts)} departments appear."))

    # 7. the old way
    plan = _old_way(scenario)
    kinds = Counter(c.kind.value for c in rules.find_clashes(scenario, plan, include_risk=False))
    digs = rules.digs_per_segment(scenario, plan)
    worst = max(digs.get(i, 0) for i in DEMO_ROADS["Munchur Road"])
    want = {"same_road": 4, "order": 3, "protected_road": 2}
    summary = f"same_road {kinds['same_road']}, order {kinds['order']}, protected_road {kinds['protected_road']} ({sum(kinds.values())} in all), most digs on one Munchur segment {worst}"
    if all(kinds[k] == n for k, n in want.items()) and sum(kinds.values()) == 9 and worst == 4:
        lines.append(("PASS", "Old way clashes: " + summary + "."))
    else:
        lines.append(("FAIL", "Old way clashes: " + summary + "; expected 4, 3, 2 (9 in all) and 4."))

    # 8. shared trenches
    groups = scenario.parallel_groups
    if len(groups) == 1 and groups[0].group_id == "G1" and sorted(groups[0].work_ids) == ["T-221", "W-104"]:
        lines.append(("PASS", f"One shared trench, G1, for T-221 and W-104; it saves {costs.inr(groups[0].saving_inr)}."))
    else:
        found = ", ".join(f"{g.group_id} ({' + '.join(g.work_ids)})" for g in groups) or "none"
        lines.append(("FAIL", f"Shared trenches: found {found}; expected only G1 for T-221 and W-104."))
    return lines


def first_fit(work: Work, blocked: set[int], after: int = -1) -> int | None:
    """The earliest start for the work's first mode that avoids the blocked days."""
    d = work.modes[0].duration_days
    for s in range(max(work.earliest_start, after + 1), work.latest_end - d + 2):
        if not any(day in blocked for day in range(s, s + d)):
            return s
    return None


def story_lines(scenario: Scenario) -> list[Line]:
    from risk import agent, weather, windows  # risk is only used here, never at import time

    label = windows.days_label
    start = scenario.start_date
    works = {w.work_id: w for w in scenario.works}
    lines: list[Line] = []

    def span(work_id: str, s: int) -> tuple[int, int]:
        return s, s + works[work_id].modes[0].duration_days - 1

    # 1. the shared trench
    w104, t221 = works["W-104"], works["T-221"]
    open_cut = [next(m.duration_days for m in w.modes if m.mode == Mode.open_cut) for w in (w104, t221)]
    first = max(w104.earliest_start, t221.earliest_start)
    last_end = min(w104.latest_end, t221.latest_end)
    common = next((s for s in range(first, last_end + 1) if s + max(open_cut) - 1 <= last_end), None)
    if common is None:
        lines.append(("FAIL", "W-104 and T-221 have no common dates for one trench."))
        trench_end = None
    else:
        trench_end = common + max(open_cut) - 1
        text = f"W-104 and T-221 can share one trench on {label(start, common, trench_end)}"
        if (common, trench_end) == (8, 13):
            lines.append(("PASS", text + "."))
        else:
            lines.append(("FAIL", text + f" (days {common} to {trench_end}); expected days 8 to 13."))

    # 2. after the trench
    g310 = first_fit(works["G-310"], set(), after=13)
    r501 = first_fit(works["R-501"], set(), after=span("G-310", g310)[1]) if g310 is not None else None
    if g310 is None or r501 is None:
        lines.append(("FAIL", "After the trench, " + ("G-310" if g310 is None else "R-501") + " has no room before day 27."))
    else:
        a, b = span("G-310", g310), span("R-501", r501)
        lines.append(("PASS", f"After the trench, G-310 fits on {label(start, *a)} and R-501 on {label(start, *b)}."))

    # 3. the procession
    event = next(w for w in scenario.risk_windows if w.window_id == "EV-DEMO")
    touched = sorted(w.work_id for w in scenario.works if set(w.segment_ids) & set(event.segment_ids))
    blocked = {12, 13, 18}
    stuck = [i for i in touched if first_fit(works[i], blocked) is None]
    d412 = first_fit(works["D-412"], blocked)
    p118 = first_fit(works["P-118"], blocked, after=span("D-412", d412)[1]) if d412 is not None else None
    if touched != ["D-412", "P-118", "W-118"]:
        lines.append(("FAIL", "The procession touches " + ", ".join(touched) + ", not D-412, P-118 and W-118."))
    elif stuck:
        lines.append(("FAIL", ", ".join(stuck) + " has no room around the rain and the procession (days 12, 13 and 18)."))
    elif p118 is None:
        lines.append(("FAIL", "P-118 has no room after D-412 around the rain and the procession."))
    else:
        lines.append(("PASS", "D-412, P-118 and W-118 all fit around the rain and the procession; D-412 then P-118 fit one after the other."))

    # 4. the rain
    ov1 = windows.RiskWindow(window_id="OV-1", kind="rain", start_day=12, end_day=13, segment_ids=[], value=70.0,
                             source="override", label="Heavy rain, 14\u201315 Nov")
    found = {w.window_id: w for w in windows.compute_risk_windows(scenario, "fixture", [ov1])}
    low = {s.segment_id for s in scenario.segments if s.low_lying}
    hit = agent.affected_works(scenario, _old_way(scenario), list(found.values()))
    munchur = [i for i in hit if "Munchur" in works[i].road_name]
    if "OV-1" not in found or set(found["OV-1"].segment_ids) != low:
        lines.append(("FAIL", "The simulated rain does not cover exactly the low-lying segments."))
    elif hit != ["D-412", "P-118", "W-118"] or munchur:
        lines.append(("FAIL", "The simulated rain hits " + (", ".join(hit) or "no works") + ", not D-412, P-118 and W-118."))
    else:
        lines.append(("PASS", f"The simulated rain covers {len(low)} low-lying segments and hits only D-412, P-118 and W-118, no Munchur Road work."))

    # 5. the forecast
    heavy = costs.policy()["risk"]["heavy_rain_mm_24h"]
    days = weather.fixture_days()
    summary = windows.daily_summary(scenario, "fixture", 8, 13)
    problems = []
    if summary != {"max_rain_mm": 18.0, "max_aqi": 88, "band": "Satisfactory"}:
        problems.append(f"days 8 to 13 give {summary}")
    if not all(days[i].aqi == 205 and weather.aqi_mod.band(days[i].aqi) == "Poor" for i in (26, 27)):
        problems.append("days 26 and 27 are not AQI 205 (Poor)")
    if any(d.rain_mm >= heavy for d in days):
        problems.append("a day reaches heavy rain")
    if problems:
        lines.append(("FAIL", "Demo forecast: " + "; ".join(problems) + "."))
    else:
        lines.append(("PASS", f"Demo forecast: days 8 to 13 have at most {summary['max_rain_mm']} mm of rain and AQI {summary['max_aqi']} ({summary['band']}); days 26 and 27 have AQI 205 (Poor); no day reaches heavy rain."))

    # 6. today
    t230 = next((a for a in _old_way(scenario).assignments if a.work_id == "T-230"), None)
    if t230 is not None and t230.start_day <= 8 <= t230.end_day:
        lines.append(("PASS", f"T-230 is open on {label(start, 8, 8)} in the old way, so the field crew has work today."))
    else:
        lines.append(("FAIL", "T-230 is not open on day 8 (10 Nov) in the old way, so the field crew has no work today."))
    return lines


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    scenario = demo_scenario()
    lines = road_lines(scenario) + story_lines(scenario)
    show(lines)
    counts = Counter(status for status, _ in lines)
    print(f"{counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failed")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
