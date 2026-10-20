import datetime as dt

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
