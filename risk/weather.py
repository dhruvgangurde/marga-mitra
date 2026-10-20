"""Daily rain and air quality for the demo calendar."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from risk import aqi as aqi_mod

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "weather_surathkal.json"

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


def daily_weather(mode: str = "fixture", now: datetime | None = None) -> list[DayWeather]:
    if mode == "fixture":
        return fixture_days()
    raise ValueError("mode must be fixture or live")
