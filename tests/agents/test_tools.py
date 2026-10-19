from datetime import date

import pytest

from agents.conflicts import detect_conflicts
from agents.tools import day_label, days_label, options_for
from contracts import costs
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import ConflictKind, Mode, RiskWindow


@pytest.fixture
def s():
    return tiny_scenario()


@pytest.fixture
def p(s):
    return fake_naive_plan(s)


@pytest.fixture
def clashes(s, p):
    return {c.conflict_id: c for c in detect_conflicts(s, p)}


def labels(opts):
    return [o.label for o in opts]


def deltas(opts):
    return [o.cost_delta_inr for o in opts]


def test_date_words(s):
    assert day_label(s, 8) == "10 Nov"
    assert days_label(s, 8, 12) == "10–14 Nov"
    assert days_label(s, 27, 30) == "29 Nov – 2 Dec"
    assert days_label(s, 18, 18) == "20 Nov"


def test_same_road_options_for_water(s, p, clashes):
    opts = options_for(clashes["C4"], s, p, "W-001")
    assert labels(opts) == ["A · Shared trench, 10–14 Nov", "B · Move after T-001, 15–19 Nov", "C · Keep 10–14 Nov"]
    assert deltas(opts) == [-336000, 10000, 0]
    assert opts[0].shared_group == "G1"
    assert opts[0].start_day == 8


def test_same_road_options_for_telecom(s, p, clashes):
    opts = options_for(clashes["C4"], s, p, "T-001")
    assert labels(opts) == ["A · Shared trench, 10–14 Nov", "B · Trenchless, 12–15 Nov", "C · Move after W-001, 15–17 Nov",
                            "D · Keep 12–14 Nov"]
    assert deltas(opts) == [-336000, 64800, 6000, 0]


def test_costs_come_from_the_cost_tables_and_fit_the_window(s, p, clashes):
    works = {w.work_id: w for w in s.works}
    for conflict in clashes.values():
        for work_id in conflict.work_ids:
            for o in options_for(conflict, s, p, work_id):
                w = works[o.work_id]
                share = s.parallel_groups[0].saving_inr // 2 if o.shared_group else 0
                assert o.cost_delta_inr == costs.move_cost_inr(w, o.start_day, o.mode, share)
                assert o.start_day >= w.earliest_start
                assert o.start_day + costs.option_for(w, o.mode).duration_days - 1 <= w.latest_end or o.shared_group


def test_move_after_is_dropped_when_it_misses_the_window(s, p, clashes):
    tight = s.model_copy(update={"works": [w.model_copy(update={"latest_end": 11}) if w.work_id == "W-001" else w
                                           for w in s.works]})
    opts = options_for(clashes["C4"], tight, p, "W-001")
    assert not any("Move after" in o.label for o in opts)


def test_unknown_work_gets_nothing(s, p, clashes):
    assert options_for(clashes["C4"], s, p, "G-001") == []
    assert options_for(clashes["C4"], s, p, "X-999") == []


def test_order_options(s, p, clashes):
    roads = options_for(clashes["C3"], s, p, "R-001")
    assert labels(roads) == ["A · Resurface after every dig, 15–17 Nov"]
    assert deltas(roads) == [8000]
    water = options_for(clashes["C3"], s, p, "W-001")
    assert labels(water) == ["A · Finish before resurfacing, 6–10 Nov"]
    assert deltas(water) == [0]
    gas = options_for(clashes["C1"], s, p, "G-001")
    assert labels(gas) == ["A · Finish before resurfacing, 7–10 Nov", "B · Trenchless, 11–15 Nov"]
    assert deltas(gas) == [0, 273600]


def test_rain_options(s, p, clashes):
    water = options_for(clashes["C6"], s, p, "W-001")
    assert labels(water) == ["A · Move after the heavy rain, 16–20 Nov", "B · Move before the heavy rain, 9–13 Nov"]
    assert deltas(water) == [12000, 0]
    telecom = options_for(clashes["C5"], s, p, "T-001")
    assert labels(telecom)[-1] == "C · Trenchless, 12–15 Nov"


def _protected(s):
    segs = [seg.model_copy(update={"protected_until": date(2029, 1, 1)}) if seg.segment_id == "S-0003" else seg
            for seg in s.segments]
    return s.model_copy(update={"segments": segs})


def test_protected_road_offers_trenchless(s, p):
    sp = _protected(s)
    clash = next(c for c in detect_conflicts(sp, p) if c.kind == ConflictKind.protected_road)
    assert clash.work_ids == ["G-001"]
    opts = options_for(clash, sp, p, "G-001")
    assert labels(opts) == ["A · Trenchless, 11–15 Nov"]
    assert deltas(opts) == [273600]


def test_protected_road_without_trenchless_has_no_option(s, p):
    sp = _protected(s)
    gas = next(w for w in sp.works if w.work_id == "G-001")
    open_only = gas.model_copy(update={"modes": [m for m in gas.modes if m.mode == Mode.open_cut]})
    sp = sp.model_copy(update={"works": [open_only if w.work_id == "G-001" else w for w in sp.works]})
    clash = next(c for c in detect_conflicts(sp, p) if c.kind == ConflictKind.protected_road)
    assert options_for(clash, sp, p, "G-001") == []


def test_event_options_have_no_trenchless(s, p):
    event = RiskWindow(window_id="EV-1", kind="event", start_day=10, end_day=10, segment_ids=["S-0003"], value=0,
                       source="event", label="Procession, 12 Nov")
    se = s.model_copy(update={"risk_windows": [event]})
    clash = next(c for c in detect_conflicts(se, p) if c.kind == ConflictKind.risk and c.work_ids == ["G-001"])
    opts = options_for(clash, se, p, "G-001")
    assert labels(opts) == ["A · Move after the procession, 13–16 Nov", "B · Move before the procession, 8–11 Nov"]
    assert deltas(opts) == [4000, 0]
