"""Daily rain and air quality for the demo calendar (demo forecast, or live Open-Meteo)."""

import json
import logging
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
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=13.0105&longitude=74.7943"
    "&daily=precipitation_sum&timezone=Asia%2FKolkata&forecast_days=16"
)
AIR_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=13.0105&longitude=74.7943"
    "&hourly=pm10,pm2_5&timezone=Asia%2FKolkata&forecast_days=5"
)

_cache: list[dict] | None = None


@dataclass(frozen=True)
class DayWeather:
    day: int
    rain_mm: float
    pm2_5: float
    pm10: float
    source: Literal["fixture", "open-meteo"]

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
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_live(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    try:
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if now - datetime.fromisoformat(cached["fetched_at"]) < CACHE_TTL:
            return cached
    except (OSError, ValueError, KeyError):
        pass
    data = {"fetched_at": now.isoformat(), "forecast": _get_json(FORECAST_URL), "air": _get_json(AIR_URL)}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, CACHE)
    return data


def overlay_live(days: list[DayWeather], raw: dict, today: int) -> list[DayWeather]:
    times = raw["forecast"]["daily"]["time"]
    rains = raw["forecast"]["daily"]["precipitation_sum"]
    first = date.fromisoformat(times[0])
    # shortcut: the demo calendar is Nov 2026, so live forecasts are placed from the demo's today; use real dates when the plan window starts today
    by_day = {d.day: d for d in days}

    def scenario_day(iso: str) -> int:
        return today + (date.fromisoformat(iso[:10]) - first).days

    changed: dict[int, dict] = {}
    for t, rain in zip(times, rains, strict=False):
        n = scenario_day(t)
        if n in by_day and rain is not None:
            changed.setdefault(n, {})["rain_mm"] = float(rain)

    hourly = raw["air"]["hourly"]
    sums: dict[str, dict[str, list[float]]] = {}
    for key in ("pm2_5", "pm10"):
        for t, v in zip(hourly["time"], hourly[key], strict=False):
            if v is not None:
                sums.setdefault(t[:10], {}).setdefault(key, []).append(v)
    for iso, vals in sums.items():
        n = scenario_day(iso)
        if n in by_day:
            for key, items in vals.items():
                changed.setdefault(n, {})[key] = sum(items) / len(items)

    return [replace(d, **changed[d.day], source="open-meteo") if d.day in changed else d for d in days]


def daily_weather(mode: str = "fixture", now: datetime | None = None) -> list[DayWeather]:
    if mode == "fixture":
        return fixture_days()
    if mode == "live":
        try:
            return overlay_live(fixture_days(), fetch_live(now), today_day())
        except Exception as e:
            log.warning("Live forecast unavailable (%s): using the demo forecast", type(e).__name__)
            return fixture_days()
    raise ValueError("mode must be fixture or live")
