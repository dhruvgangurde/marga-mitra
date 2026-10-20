"""Daily rain and air quality for the demo calendar (demo forecast, or live Open-Meteo)."""

import json
import logging
import math
import os
import urllib.request
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from risk import aqi as aqi_mod

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "weather_surathkal.json"
CACHE = ROOT / "data" / "raw" / "weather_cache.json"
CACHE_TTL = timedelta(hours=3)
USER_AGENT = "MargaMitra/0.1 (ChronoForge 2026, NITK Surathkal)"
RETRY_AFTER = timedelta(minutes=10)
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=13.0105&longitude=74.7943"
    "&daily=precipitation_sum&timezone=Asia%2FKolkata&forecast_days=16"
)
AIR_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=13.0105&longitude=74.7943"
    "&hourly=pm10,pm2_5&timezone=Asia%2FKolkata&forecast_days=5"
)

_cache: list[dict] | None = None
_failed_at: datetime | None = None


@dataclass(frozen=True)
class DayWeather:
    day: int
    rain_mm: float
    pm2_5: float
    pm10: float
    source: Literal["fixture", "open-meteo"]
    rain_live: bool = False
    air_live: bool = False

    @property
    def aqi(self) -> int:
        return aqi_mod.india_aqi(self.pm2_5, self.pm10)


def fixture_days() -> list[DayWeather]:
    global _cache
    if _cache is None:
        if not FIXTURE.exists():
            raise FileNotFoundError(f"Weather fixture not found: {FIXTURE}")
        _cache = json.loads(FIXTURE.read_text(encoding="utf-8"))["days"]
    return [DayWeather(d["day"], d["rain_mm"], d["pm2_5"], d["pm10"], "fixture") for d in _cache]


def today_day() -> int:
    return int(os.environ.get("TODAY_DAY", "8"))


def _get_json(url: str) -> dict:
    """The only network call in the risk package."""
    # two calls of at most 8 s, and the backend waits for them inside a request
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _read_cache(now: datetime) -> dict | None:
    try:
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if not isinstance(cached, dict):
            return None
        fetched = datetime.fromisoformat(cached["fetched_at"])
        if (
            fetched.tzinfo is not None
            and isinstance(cached.get("forecast"), dict)
            and isinstance(cached.get("air"), dict)
            and now - fetched < CACHE_TTL
        ):
            return cached
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _write_cache(content: dict) -> None:
    tmp = CACHE.with_suffix(".tmp")
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(content), encoding="utf-8")
        os.replace(tmp, CACHE)
    except OSError as e:
        log.warning("Could not save the forecast cache (%s)", type(e).__name__)


def fetch_live(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    cached = _read_cache(now)
    if cached is not None:
        return cached
    data = {"fetched_at": now.isoformat(), "forecast": _get_json(FORECAST_URL), "air": _get_json(AIR_URL)}
    _write_cache(data)
    return data


def reset_live_state() -> None:
    global _failed_at
    _failed_at = None


def _number(x: object, low: float, high: float) -> float | None:
    if isinstance(x, bool) or not isinstance(x, int | float):
        return None
    value = float(x)
    return value if math.isfinite(value) and low <= value <= high else None


def _rain_by_date(forecast: dict) -> dict[str, float]:
    times = forecast["daily"]["time"]
    rains = forecast["daily"]["precipitation_sum"]
    if not (isinstance(times, list) and isinstance(rains, list) and len(times) == len(rains)):
        raise ValueError("forecast: lengths differ")
    out: dict[str, float] = {}
    for t, v in zip(times, rains, strict=True):
        try:
            iso = date.fromisoformat(t).isoformat()
        except (TypeError, ValueError):
            raise ValueError("forecast: bad date") from None
        value = _number(v, 0, 1000)
        if value is not None:
            out[iso] = value
    return out


def _air_by_date(air: dict) -> dict[str, tuple[float | None, float | None]]:
    hourly = air["hourly"]
    times, pm25, pm10 = hourly["time"], hourly["pm2_5"], hourly["pm10"]
    if not all(isinstance(x, list) for x in (times, pm25, pm10)) or not len(times) == len(pm25) == len(pm10):
        raise ValueError("air quality: lengths differ")
    sums: dict[str, tuple[list[float], list[float]]] = {}
    for t, a, b in zip(times, pm25, pm10, strict=True):
        try:
            datetime.fromisoformat(t)
        except (TypeError, ValueError):
            raise ValueError("air quality: bad time") from None
        lists = sums.setdefault(t[:10], ([], []))
        for target, v in ((lists[0], a), (lists[1], b)):
            value = _number(v, 0, 2000)
            if value is not None:
                target.append(value)
    return {
        iso: tuple(sum(items) / len(items) if items else None for items in lists)  # type: ignore[misc]
        for iso, lists in sums.items()
    }


def overlay_live(days: list[DayWeather], raw: dict, today: int) -> list[DayWeather]:
    rains = _rain_by_date(raw["forecast"])
    air = _air_by_date(raw["air"])
    first = date.fromisoformat(raw["forecast"]["daily"]["time"][0])
    # shortcut: the demo calendar is Nov 2026, so live forecasts are placed from the demo's today; use real dates when the plan window starts today
    known = {d.day for d in days}

    def scenario_day(iso: str) -> int:
        return today + (date.fromisoformat(iso[:10]) - first).days

    changed: dict[int, dict] = {}
    for iso, rain in rains.items():
        n = scenario_day(iso)
        if n in known:
            changed.setdefault(n, {}).update(rain_mm=rain, rain_live=True)
    for iso, (pm25, pm10) in air.items():
        n = scenario_day(iso)
        if n not in known:
            continue
        for key, value in (("pm2_5", pm25), ("pm10", pm10)):
            if value is not None:
                changed.setdefault(n, {}).update({key: value, "air_live": True})

    return [replace(d, **changed[d.day], source="open-meteo") if d.day in changed else d for d in days]


def daily_weather(mode: str = "fixture", now: datetime | None = None) -> list[DayWeather]:
    global _failed_at
    if mode == "fixture":
        return fixture_days()
    if mode == "live":
        now = now or datetime.now(UTC)
        if _failed_at is not None and now - _failed_at < RETRY_AFTER:
            return fixture_days()
        try:
            days = overlay_live(fixture_days(), fetch_live(now), today_day())
        except Exception as e:
            _failed_at = now
            detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            log.warning("Live forecast unavailable (%s): using the demo forecast", detail)
            return fixture_days()
        _failed_at = None
        return days
    raise ValueError("mode must be fixture or live")
