import datetime as dt
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from contracts import costs
from risk import weather


def test_fixture_has_28_dated_days():
    days = weather.fixture_days()
    assert [d.day for d in days] == list(range(28))
    raw = weather.json.loads(weather.FIXTURE.read_text(encoding="utf-8"))["days"]
    assert raw[0]["date"] == "2026-11-02"
    assert raw[-1]["date"] == "2026-11-29"
    for d in raw:
        assert d["date"] == str(dt.date(2026, 11, 2) + dt.timedelta(d["day"]))


def test_no_heavy_rain_in_fixture():
    limit = costs.policy()["risk"]["heavy_rain_mm_24h"]
    assert all(d.rain_mm < limit for d in weather.fixture_days())


def test_demo_week_values():
    days = weather.fixture_days()
    assert max(d.rain_mm for d in days[8:14]) == 18.0
    assert max(d.aqi for d in days[8:14]) == 88


def test_poor_air_days():
    days = weather.fixture_days()
    for i in (26, 27):
        assert days[i].aqi == 205
        assert weather.aqi_mod.band(days[i].aqi) == "Poor"
    assert all(70 <= d.aqi <= 111 for d in days if d.day not in (26, 27))


def test_sources_and_new_list():
    a = weather.daily_weather("fixture")
    assert all(d.source == "fixture" for d in a)
    a.clear()
    assert len(weather.daily_weather("fixture")) == 28


def test_bad_mode():
    with pytest.raises(ValueError):
        weather.daily_weather("other")


SAMPLES = Path(__file__).parent / "samples"
T0 = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def _sample(url):
    name = "air_quality.json" if "air-quality" in url else "forecast.json"
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def live(monkeypatch, tmp_path):
    calls = []

    def fake(url):
        calls.append(url)
        return _sample(url)

    monkeypatch.setattr(weather, "_get_json", fake)
    monkeypatch.setattr(weather, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("TODAY_DAY", "8")
    return calls


def test_live_overlay(live):
    days = weather.daily_weather("live", T0)
    assert len(days) == 28
    d8, d9, d10, d7 = days[8], days[9], days[10], days[7]
    assert (d8.rain_mm, d8.pm2_5, d8.pm10, d8.aqi, d8.source) == (0.4, 50.0, 70.0, 83, "open-meteo")
    assert (d9.rain_mm, d9.pm2_5, d9.pm10, d9.aqi, d9.source) == (62.0, 95.0, 220.0, 215, "open-meteo")
    assert (d10.rain_mm, d10.aqi, d10.source) == (9.4, 88, "fixture")
    assert d7.source == "fixture"


def test_live_other_today(live, monkeypatch):
    monkeypatch.setenv("TODAY_DAY", "26")
    days = weather.daily_weather("live", T0)
    assert [d.day for d in days if d.source == "open-meteo"] == [26, 27]
    monkeypatch.setenv("TODAY_DAY", "0")
    days = weather.daily_weather("live", T0)
    assert [d.day for d in days if d.source == "open-meteo"] == [0, 1]


def test_live_cache(live):
    weather.daily_weather("live", T0)
    assert len(live) == 2
    weather.daily_weather("live", T0 + timedelta(hours=2, minutes=59))
    assert len(live) == 2
    weather.daily_weather("live", T0 + timedelta(hours=3, minutes=1))
    assert len(live) == 4


@pytest.mark.parametrize("bad", ["offline", "empty"])
def test_live_fallback(monkeypatch, tmp_path, caplog, bad):
    def fake(url):
        if bad == "offline":
            raise urllib.error.URLError("offline")
        return {}

    monkeypatch.setattr(weather, "_get_json", fake)
    monkeypatch.setattr(weather, "CACHE", tmp_path / "cache.json")
    with caplog.at_level("WARNING"):
        days = weather.daily_weather("live", T0)
    assert days == weather.fixture_days()
    assert "Live forecast unavailable" in caplog.text
