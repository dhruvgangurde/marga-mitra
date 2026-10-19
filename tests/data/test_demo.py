import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from contracts import costs, rules
from contracts.models import Dept, Mode, RiskKind, Scenario
from data.demo import DEMO_ROADS, city_segments, demo_scenario

pytestmark = pytest.mark.usefixtures("need_snapshot")

OC, TL = Mode.open_cut, Mode.trenchless
# id, dept, title, road, metres, requested day, days, first mode, earliest_start, latest_end, priority, depends_on, done
TABLE = [
    ("W-104", Dept.water, "Water main", "Munchur Road", 620, 7, 6, OC, 7, 15, 4, [], False),
    ("T-221", Dept.telecom, "Fibre duct", "Munchur Road", 620, 10, 4, OC, 8, 27, 3, [], False),
    ("G-310", Dept.gas, "Gas line", "Munchur Road east", 480, 8, 5, OC, 8, 27, 3, [], False),
    ("R-501", Dept.roads, "Resurfacing", "Munchur Road", 1100, 9, 4, OC, 9, 27, 3, ["W-104", "T-221", "G-310"], False),
    ("D-412", Dept.drainage, "Storm-water drain", "NH-66 service road", 300, 11, 4, OC, 11, 27, 4, [], False),
    ("P-118", Dept.power, "Cable shifting", "Krishnapura cross road", 210, 11, 3, OC, 11, 27, 3, [], False),
    ("W-118", Dept.water, "Service line", "Idya lane", 90, 12, 2, OC, 12, 27, 3, [], False),
    ("T-230", Dept.telecom, "Fibre to tower", "Hosabettu cross road", 350, 7, 3, TL, 7, 27, 3, [], False),
    ("D-415", Dept.drainage, "Drain repair", "Chokkabettu lane", 140, 0, 4, OC, 0, 27, 3, [], True),
    ("P-120", Dept.power, "Streetlight cable", "NITK Beach Road", 400, 14, 3, OC, 14, 27, 2, [], False),
    ("G-305", Dept.gas, "Service connections", "Hosabettu Road", 260, 5, 3, OC, 5, 27, 3, [], False),
    ("W-109", Dept.water, "Valve replacement", "Srinivasnagar road", 120, 3, 2, OC, 3, 27, 3, [], False),
    ("D-420", Dept.drainage, "Culvert cleaning", "Katipalla road", 180, 16, 3, OC, 16, 27, 3, [], False),
    ("T-240", Dept.telecom, "Fibre duct", "Kana road", 500, 15, 4, OC, 15, 27, 3, [], False),
    ("R-505", Dept.roads, "Pothole patching", "Surathkal market road", 300, 20, 2, OC, 20, 27, 2, [], False),
    ("P-125", Dept.power, "Transformer cable", "Kulai road", 150, 6, 2, OC, 6, 27, 3, [], False),
]


@pytest.fixture(scope="module")
def scenario() -> Scenario:
    return demo_scenario()


def test_scenario_basics(scenario):
    assert scenario.seed == 1
    assert scenario.start_date == date(2026, 11, 2)
    assert scenario.horizon_days == 28
    assert len(scenario.segments) > 100


def test_works_match_the_table(scenario):
    assert [w.work_id for w in scenario.works] == [row[0] for row in TABLE]
    for w, row in zip(scenario.works, TABLE, strict=True):
        wid, dept, title, road, metres, day, days, first, earliest, latest, priority, depends, done = row
        assert (w.dept, w.title, w.road_name, w.length_m) == (dept, title, road, metres), wid
        assert (w.requested_start, w.earliest_start, w.latest_end) == (day, earliest, latest), wid
        assert (w.priority, w.depends_on, w.done) == (priority, depends, done), wid
        assert w.modes[0].mode == first and w.modes[0].duration_days == days, wid
        if len(w.modes) == 2:
            other = w.modes[1]
            assert other.mode != first
            assert other.duration_days == (days + 1 if first == OC else days - 1), wid
        assert w.deposit_inr == costs.deposit_inr(dept, metres, first), wid


def test_munchur_is_five_connected_segments(scenario):
    by_id = {s.segment_id: s for s in scenario.segments}
    ids = DEMO_ROADS["Munchur Road"]
    assert len(ids) == 5
    for a, b in zip(ids, ids[1:], strict=False):
        assert b in by_id[a].neighbors
    assert not any(by_id[i].low_lying for i in ids)
    assert 900 <= sum(by_id[i].length_m for i in ids) <= 1400


def test_munchur_works_use_the_right_segments(scenario):
    works = {w.work_id: w for w in scenario.works}
    munchur = DEMO_ROADS["Munchur Road"]
    assert works["W-104"].segment_ids == munchur[0:3]
    assert works["T-221"].segment_ids == munchur[0:3]
    assert works["G-310"].segment_ids == munchur[2:5]
    assert works["R-501"].segment_ids == munchur


def test_junction_is_shared_by_exactly_one_segment(scenario):
    works = {w.work_id: w for w in scenario.works}
    assert len(set(works["D-412"].segment_ids) & set(works["P-118"].segment_ids)) == 1
    assert not set(works["W-118"].segment_ids) & set(works["D-412"].segment_ids)
    assert not set(works["W-118"].segment_ids) & set(works["P-118"].segment_ids)


def test_story_roads_are_low_lying(scenario):
    by_id = {s.segment_id: s for s in scenario.segments}
    works = {w.work_id: w for w in scenario.works}
    for wid in ("D-412", "P-118", "W-118"):
        assert all(by_id[i].low_lying for i in works[wid].segment_ids), wid


def test_protected_roads(scenario):
    by_id = {s.segment_id: s for s in scenario.segments}
    works = {w.work_id: w for w in scenario.works}
    assert all(by_id[i].protected_until == date(2028, 1, 14) for i in works["P-120"].segment_ids)
    assert all(by_id[i].protected_until == date(2029, 3, 3) for i in works["G-305"].segment_ids)
    protected = {s.segment_id for s in scenario.segments if s.protected_until}
    touching = {w.work_id for w in scenario.works if protected & set(w.segment_ids)}
    assert touching == {"P-120", "G-305"}


def test_procession(scenario):
    assert len(scenario.risk_windows) == 1
    window = scenario.risk_windows[0]
    assert (window.window_id, window.kind, window.start_day, window.end_day) == ("EV-DEMO", RiskKind.event, 18, 18)
    assert window.label == "Procession, 20 Nov"
    expected = set(DEMO_ROADS["NH-66 service road"]) | set(DEMO_ROADS["Idya lane"])
    assert set(window.segment_ids) == expected


def test_one_shared_trench(scenario):
    assert len(scenario.parallel_groups) == 1
    group = scenario.parallel_groups[0]
    assert group.group_id == "G1"
    assert group.work_ids == ["T-221", "W-104"]
    assert group.saving_inr > 0


def test_segments_cover_each_work(scenario):
    by_id = {s.segment_id: s for s in scenario.segments}
    for w in scenario.works:
        assert sum(by_id[i].length_m for i in w.segment_ids) >= 0.75 * w.length_m, w.work_id


def test_old_way_clashes(scenario, naive):
    plan = naive(scenario)
    clashes = rules.find_clashes(scenario, plan, include_risk=False)
    assert Counter(c.kind.value for c in clashes) == {"same_road": 4, "order": 3, "protected_road": 2}
    pairs = {tuple(c.work_ids) for c in clashes if c.kind.value == "same_road"}
    assert pairs == {("T-221", "W-104"), ("G-310", "W-104"), ("G-310", "T-221"), ("D-412", "P-118")}
    assert rules.clash_count(scenario, plan) == 9
    digs = rules.digs_per_segment(scenario, plan)
    assert max(digs[i] for i in DEMO_ROADS["Munchur Road"]) == 4


def test_city_segments_are_fresh_copies():
    first = city_segments()
    first[0].lanes = 99
    assert city_segments()[0].lanes != 99


def test_out_file_parses_back(scenario, tmp_path):
    target = tmp_path / "scenario.json"
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, "-m", "data.demo", "--out", str(target)], cwd=root, check=True)
    assert Scenario.model_validate_json(target.read_text(encoding="utf-8")) == scenario
