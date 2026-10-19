import pytest

from agents.conflicts import cluster_conflicts, detect_conflicts
from agents.coordinator import between_label, current, is_keep, listing, work_clash, work_options
from agents.tools import options_for
from contracts.fakes import fake_naive_plan, tiny_scenario


@pytest.fixture
def s():
    return tiny_scenario()


@pytest.fixture
def p(s):
    return fake_naive_plan(s)


@pytest.fixture
def cluster(s, p):
    return cluster_conflicts(detect_conflicts(s, p))[0]


def labels(opts):
    return [o.label for o in opts]


def costs_of(opts):
    return [o.cost_delta_inr for o in opts]


def test_options_for_water_across_the_cluster(s, p, cluster):
    opts = work_options(cluster, s, p, "W-001")
    assert labels(opts) == ["A · Finish before resurfacing, 6–10 Nov", "B · Shared trench, 10–14 Nov",
                            "C · Move after T-001, 15–19 Nov", "D · Keep 10–14 Nov",
                            "E · Move after the heavy rain, 16–20 Nov", "F · Move before the heavy rain, 9–13 Nov"]
    assert costs_of(opts) == [0, -336000, 10000, 0, 12000, 0]


def test_options_for_telecom_across_the_cluster(s, p, cluster):
    opts = work_options(cluster, s, p, "T-001")
    assert labels(opts) == ["A · Finish before resurfacing, 8–10 Nov", "B · Trenchless, 12–15 Nov",
                            "C · Shared trench, 10–14 Nov", "D · Move after W-001, 15–17 Nov", "E · Keep 12–14 Nov",
                            "F · Move after the heavy rain, 16–18 Nov", "G · Move before the heavy rain, 11–13 Nov"]
    assert costs_of(opts) == [0, 64800, -336000, 6000, 0, 8000, 0]


def test_options_for_roads_and_gas(s, p, cluster):
    roads = work_options(cluster, s, p, "R-001")
    assert labels(roads) == ["A · Resurface after every dig, 15–17 Nov"]
    assert costs_of(roads) == [8000]
    gas = work_options(cluster, s, p, "G-001")
    assert labels(gas) == ["A · Finish before resurfacing, 7–10 Nov", "B · Trenchless, 11–15 Nov"]
    assert costs_of(gas) == [0, 273600]


def test_a_work_outside_the_cluster_has_no_options(s, p, cluster):
    assert work_options(cluster, s, p, "X-999") == []


def test_work_clash_joins_every_note_of_the_work(cluster):
    clash = work_clash(cluster, "G-001")
    assert clash.conflict_id == "C1"
    assert clash.note == "G-001 digs Test Road during or after resurfacing R-001."
    water = work_clash(cluster, "W-001")
    assert water.conflict_id == "C3"
    assert water.note.count(".") == 3
    assert "W-001 is open during Heavy rain, 14–15 Nov." in water.note


def test_current_falls_back_to_the_departments_ask(s, p):
    water = next(w for w in s.works if w.work_id == "W-001")
    assert current(p, water) == (8, water.modes[0].mode)
    empty = p.model_copy(update={"assignments": []})
    assert current(empty, water) == (8, water.modes[0].mode)


def test_only_the_keep_options_keep(s, p, cluster):
    works = {w.work_id: w for w in s.works}
    for work_id in ("W-001", "T-001", "R-001", "G-001"):
        keeps = [o.label for o in work_options(cluster, s, p, work_id) if is_keep(o, p, works[work_id])]
        expected = {"W-001": ["D · Keep 10–14 Nov"], "T-001": ["E · Keep 12–14 Nov"]}.get(work_id, [])
        assert keeps == expected


def _in_one_trench(p, t_start=8, t_end=12):
    moved = []
    for a in p.assignments:
        if a.work_id == "W-001":
            a = a.model_copy(update={"start_day": 8, "end_day": 12, "shared_group": "G1"})
        elif a.work_id == "T-001":
            a = a.model_copy(update={"start_day": t_start, "end_day": t_end, "shared_group": "G1"})
        moved.append(a)
    return p.model_copy(update={"assignments": moved})


def test_a_work_already_in_a_trench_keeps_it(s, p, cluster):
    shared = _in_one_trench(p)
    c4 = next(c for c in cluster if c.conflict_id == "C4")
    water = next(w for w in s.works if w.work_id == "W-001")
    opts = options_for(c4, s, shared, "W-001")
    # Phase 1 drops a Keep that repeats the trench option, so the trench option is the one that keeps
    kept = [o for o in opts if o.shared_group == "G1" and o.start_day == 8]
    assert len(kept) == 1
    assert is_keep(kept[0], shared, water)
    assert not is_keep(next(o for o in opts if o.label.startswith("B")), shared, water)


def test_keep_copies_the_trench_when_it_differs_from_the_trench_option(s, p, cluster):
    shared = _in_one_trench(p, t_start=6, t_end=8)
    c4 = next(c for c in cluster if c.conflict_id == "C4")
    water = next(w for w in s.works if w.work_id == "W-001")
    opts = options_for(c4, s, shared, "W-001")
    keep = next(o for o in opts if " Keep " in o.label)
    assert keep.shared_group == "G1"
    assert keep.start_day == 8
    assert is_keep(keep, shared, water)
    trench = next(o for o in opts if " Shared trench" in o.label)
    assert not is_keep(trench, shared, water)


def test_listing():
    assert listing(["W-001"]) == "W-001"
    assert listing(["W-001", "T-001"]) == "W-001 and T-001"
    assert listing(["W-001", "T-001", "G-001"]) == "W-001, T-001 and G-001"


def test_between_label(s):
    assert between_label(s, 9, 12) == "11 and 14 Nov"
    assert between_label(s, 28, 30) == "30 Nov and 2 Dec"
