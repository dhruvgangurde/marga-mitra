import json
from datetime import date
from pathlib import Path

import pytest

from contracts import fakes
from contracts.models import RiskWindow
from data.demo import demo_scenario
from risk import weather
from risk.weather import DayWeather
from risk.windows import compute_risk_windows, daily_summary, days_label, main

OV1 = RiskWindow(window_id="OV-1", kind="rain", start_day=12, end_day=13, segment_ids=[], value=70.0,
                 source="override", label="Heavy rain, 14–15 Nov")
START = date(2026, 11, 2)
SAMPLES = Path(__file__).parent / "samples"


@pytest.fixture
def demo(need_snapshot):
    return demo_scenario()


def test_days_label():
    assert days_label(START, 12, 13) == "14–15 Nov"
    assert days_label(START, 18, 18) == "20 Nov"
    assert days_label(START, 26, 27) == "28–29 Nov"
    assert days_label(START, 27, 30) == "29 Nov – 2 Dec"


def test_demo_fixture(demo):
    ws = compute_risk_windows(demo, "fixture")
    assert [w.window_id for w in ws] == ["EV-DEMO", "A1"]
    a1 = ws[1]
    assert (a1.kind, a1.start_day, a1.end_day, a1.value, a1.source) == ("air", 26, 27, 205.0, "fixture")
    assert a1.label == "Poor air, 28–29 Nov"
    assert a1.segment_ids == [s.segment_id for s in demo.segments]


def test_rain_override(demo):
    ws = compute_risk_windows(demo, "fixture", [OV1])
    assert [w.window_id for w in ws] == ["OV-1", "EV-DEMO", "A1"]
    ids = set(ws[0].segment_ids)
    assert ids == {s.segment_id for s in demo.segments if s.low_lying}
    for wid in ("D-412", "P-118", "W-118"):
        work = next(w for w in demo.works if w.work_id == wid)
        assert set(work.segment_ids) <= ids
    for work in demo.works:
        if "Munchur" in work.road_name:
            assert not set(work.segment_ids) & ids


def test_air_and_event_overrides(demo):
    air = RiskWindow(window_id="OV-2", kind="air", start_day=3, end_day=4, segment_ids=[], value=250.0,
                     source="override", label="Poor air, 5–6 Nov")
    ev = RiskWindow(window_id="OV-3", kind="event", start_day=5, end_day=5, segment_ids=["S-0001"], value=0.0,
                    source="override", label="Event, 7 Nov")
    ws = {w.window_id: w for w in compute_risk_windows(demo, "fixture", [air, ev])}
    assert ws["OV-2"].segment_ids == [s.segment_id for s in demo.segments]
    assert ws["OV-3"].segment_ids == ["S-0001"]


def test_repeatable(demo):
    a = compute_risk_windows(demo, "fixture", [OV1])
    assert a == compute_risk_windows(demo, "fixture", [OV1])
    held = demo.model_copy(update={"risk_windows": compute_risk_windows(demo, "fixture")})
    assert compute_risk_windows(held, "fixture") == compute_risk_windows(demo, "fixture")


def test_synthetic_rain(monkeypatch):
    rain = {3: 60.0, 4: 58.5, 10: 55.0, 20: 50.0, 22: 49.9}
    days = [DayWeather(d, rain.get(d, 0.0), 40, 60, "fixture") for d in range(28)]
    monkeypatch.setattr(weather, "daily_weather", lambda mode="fixture", now=None: days)
    ws = compute_risk_windows(fakes.tiny_scenario(), "fixture")
    assert [(w.window_id, w.start_day, w.end_day, w.value, w.label) for w in ws] == [
        ("R1", 3, 4, 60.0, "Heavy rain, 5–6 Nov"),
        ("R2", 10, 10, 55.0, "Heavy rain, 12 Nov"),
        ("R3", 20, 20, 50.0, "Heavy rain, 22 Nov"),
    ]
    assert all(w.segment_ids == ["S-0002"] for w in ws)


def test_live_mode(demo, monkeypatch, tmp_path):
    def fake(url):
        name = "air_quality.json" if "air-quality" in url else "forecast.json"
        return json.loads((SAMPLES / name).read_text(encoding="utf-8"))

    monkeypatch.setattr(weather, "_get_json", fake)
    monkeypatch.setattr(weather, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("TODAY_DAY", "8")
    ws = {w.window_id: w for w in compute_risk_windows(demo, "live")}
    r1, a1, a2 = ws["R1"], ws["A1"], ws["A2"]
    assert (r1.start_day, r1.end_day, r1.value, r1.label, r1.source) == (9, 9, 62.0, "Heavy rain, 11 Nov", "open-meteo")
    assert (a1.start_day, a1.end_day, a1.value, a1.label, a1.source) == (9, 9, 215.0, "Poor air, 11 Nov", "open-meteo")
    assert (a2.start_day, a2.end_day, a2.label, a2.source) == (26, 27, "Poor air, 28–29 Nov", "fixture")


def test_daily_summary(demo):
    assert daily_summary(demo, "fixture", 8, 13) == {"max_rain_mm": 18.0, "max_aqi": 88, "band": "Satisfactory"}
    clamped = daily_summary(demo, "fixture", 26, 30)
    assert (clamped["max_aqi"], clamped["band"]) == (205, "Poor")


def test_main(demo, capsys, monkeypatch):
    monkeypatch.setenv("TODAY_DAY", "8")
    main(["--seed", "1"])
    out = capsys.readouterr().out
    assert "Risk windows · test case 1 · fixture" in out
    assert any(line.startswith("A1") for line in out.splitlines())
    assert "Forecast for 10–15 Nov: highest rain 18.0 mm in 24 hours · AQI 88 · Satisfactory" in out
