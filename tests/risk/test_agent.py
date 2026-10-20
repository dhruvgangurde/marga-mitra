import pytest

from contracts import fakes
from contracts.models import Mode, RiskWindow
from data.demo import demo_scenario
from risk.agent import affected_works
from risk.windows import compute_risk_windows

OV1 = RiskWindow(window_id="OV-1", kind="rain", start_day=12, end_day=13, segment_ids=[], value=70.0,
                 source="override", label="Heavy rain, 14-15 Nov")


def _window(wid, kind, a, b, segs):
    return RiskWindow(window_id=wid, kind=kind, start_day=a, end_day=b, segment_ids=segs, value=0.0,
                      source="fixture", label="test")


def _trenchless(plan, work_id):
    items = [a.model_copy(update={"mode": Mode.trenchless}) if a.work_id == work_id else a
             for a in plan.assignments]
    return plan.model_copy(update={"assignments": items})


@pytest.fixture
def tiny():
    s = fakes.tiny_scenario()
    return s, fakes.fake_naive_plan(s)


def test_rain_window(tiny):
    s, plan = tiny
    rain = _window("R1", "rain", 12, 13, ["S-0002"])
    assert affected_works(s, plan, [rain]) == ["T-001", "W-001"]
    assert affected_works(s, _trenchless(plan, "T-001"), [rain]) == ["W-001"]


def test_event_window(tiny):
    s, plan = tiny
    ev = _window("EV-1", "event", 10, 10, ["S-0003"])
    assert affected_works(s, plan, [ev]) == ["G-001", "R-001"]
    assert affected_works(s, _trenchless(plan, "G-001"), [ev]) == ["G-001", "R-001"]


def test_done_and_duplicates(tiny):
    s, plan = tiny
    rain = _window("R1", "rain", 12, 13, ["S-0002"])
    other = _window("R2", "rain", 8, 9, ["S-0001"])
    works = [w.model_copy(update={"done": True}) if w.work_id == "W-001" else w for w in s.works]
    done = s.model_copy(update={"works": works})
    assert "W-001" not in affected_works(done, plan, [rain])
    assert affected_works(s, plan, [rain, other]).count("W-001") == 1
    assert affected_works(s, plan, []) == []


def test_demo(need_snapshot, old_way):
    demo = demo_scenario()
    windows = compute_risk_windows(demo, "fixture", [OV1])
    assert affected_works(demo, old_way(demo), windows) == ["D-412", "P-118", "W-118"]
