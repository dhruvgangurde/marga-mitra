import json
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from risk import weather

SAMPLES = Path(__file__).parent / "samples"
T0 = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def _sample(url):
    name = "air_quality.json" if "air-quality" in url else "forecast.json"
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


class Fake:
    """A fake _get_json that counts its calls."""

    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def __call__(self, url):
        self.calls += 1
        if self.error:
            raise self.error
        return _sample(url)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = Fake()
    monkeypatch.setattr(weather, "_get_json", f)
    monkeypatch.setattr(weather, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("TODAY_DAY", "8")
    return f


def test_broken_cache_is_replaced(fake):
    weather.CACHE.write_text("{not json", encoding="utf-8")
    days = weather.daily_weather("live", T0)
    assert fake.calls == 2
    assert (days[9].rain_mm, days[9].source) == (62.0, "open-meteo")
    assert isinstance(json.loads(weather.CACHE.read_text(encoding="utf-8")), dict)


def test_cache_without_fetched_at(fake):
    weather.CACHE.write_text(json.dumps({"forecast": {}, "air": {}}), encoding="utf-8")
    weather.daily_weather("live", T0)
    assert fake.calls == 2


def test_unwritable_cache_still_gives_live_days(fake, tmp_path, caplog):
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    weather.CACHE = tmp_path / "file.txt" / "weather_cache.json"
    with caplog.at_level("WARNING"):
        days = weather.daily_weather("live", T0)
    assert days[9].source == "open-meteo"
    assert "Could not save the forecast cache" in caplog.text


def test_failure_is_remembered_for_ten_minutes(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(weather, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("TODAY_DAY", "8")
    down = Fake(error=urllib.error.URLError("offline"))
    monkeypatch.setattr(weather, "_get_json", down)
    with caplog.at_level("WARNING"):
        assert weather.daily_weather("live", T0) == weather.fixture_days()
    assert down.calls == 1
    assert caplog.text.count("Live forecast unavailable") == 1

    with caplog.at_level("WARNING"):
        assert weather.daily_weather("live", T0 + timedelta(minutes=5)) == weather.fixture_days()
    assert down.calls == 1
    assert caplog.text.count("Live forecast unavailable") == 1

    up = Fake()
    monkeypatch.setattr(weather, "_get_json", up)
    days = weather.daily_weather("live", T0 + timedelta(minutes=11))
    assert up.calls == 2
    assert days[9].source == "open-meteo"


def _run(monkeypatch, tmp_path, change=None):
    """Run live mode with the samples after change(forecast, air) edited them."""
    forecast, air = _sample("forecast"), _sample("air-quality")
    if change:
        change(forecast, air)

    def fake(url):
        return air if "air-quality" in url else forecast

    monkeypatch.setattr(weather, "_get_json", fake)
    monkeypatch.setattr(weather, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("TODAY_DAY", "8")
    return weather.daily_weather("live", T0)


def test_samples_mark_live_days(monkeypatch, tmp_path):
    days = _run(monkeypatch, tmp_path)
    assert days[8].rain_live and days[8].air_live
    assert days[9].rain_live and days[9].air_live
    assert not days[10].rain_live and not days[10].air_live
    assert days[10].source == "fixture"


@pytest.mark.parametrize(
    ("change", "text"),
    [
        (lambda f, a: f["daily"]["precipitation_sum"].pop(), "forecast: lengths differ"),
        (lambda f, a: a["hourly"]["pm10"].pop(), "air quality: lengths differ"),
        (lambda f, a: f["daily"]["time"].__setitem__(0, "24-10-2026"), "forecast: bad date"),
        (lambda f, a: a["hourly"]["time"].__setitem__(0, "nonsense"), "air quality: bad time"),
    ],
)
def test_broken_answers_fall_back(monkeypatch, tmp_path, caplog, change, text):
    with caplog.at_level("WARNING"):
        days = _run(monkeypatch, tmp_path, change)
    assert days == weather.fixture_days()
    assert text in caplog.text


@pytest.mark.parametrize("bad", ["62", -3.0, True, float("nan"), 1500.0])
def test_bad_rain_values_are_left_out(monkeypatch, tmp_path, bad):
    days = _run(monkeypatch, tmp_path, lambda f, a: f["daily"]["precipitation_sum"].__setitem__(1, bad))
    assert days[9].rain_mm == weather.fixture_days()[9].rain_mm
    assert not days[9].rain_live


def test_one_pollutant_missing(monkeypatch, tmp_path):
    def change(f, a):
        a["hourly"]["pm10"] = [None if t.startswith("2026-10-25") else v for t, v in zip(a["hourly"]["time"], a["hourly"]["pm10"], strict=True)]

    days = _run(monkeypatch, tmp_path, change)
    assert days[9].pm2_5 == 95.0
    assert days[9].pm10 == weather.fixture_days()[9].pm10
    assert days[9].air_live
