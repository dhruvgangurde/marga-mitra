"""What the copilot does with no model set up: a few fixed rules for the demo questions."""
from __future__ import annotations

import re

from agents.copilot_tools import LAST_DAY, Next

HELP = ("I can show the works on a road, move the day, simulate rain or open a work. "
        "Try: show every dig on Munchur Road next week.")

ID = re.compile(r"\b[A-Z]-\d{3}\b", re.IGNORECASE)
ROAD = re.compile(r"[\w-]+\s+(?:road|lane)\b", re.IGNORECASE)
DATE = re.compile(r"(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?\s+Nov", re.IGNORECASE)
WHAT_IF = re.compile(r"\bwhat\s+if\b", re.IGNORECASE)
DAYS = re.compile(r"(\d+)\s+days?\b", re.IGNORECASE)
RAIN = re.compile(r"\b(?:rain|storm)\b", re.IGNORECASE)
WHY = re.compile(r"\bwhy\b", re.IGNORECASE)
MM = re.compile(r"(\d+)\s*mm", re.IGNORECASE)
DEFAULT_RAIN = (12, 13, 70.0)  # the demo story: 14–15 Nov, 70 mm
FIRST_NOV_DAY = 2  # day 0 is 2 Nov, so a date in November is the number minus 2


def _days_of(message: str) -> tuple[int, int] | None:
    found = DATE.search(message)
    if found is None:
        return DEFAULT_RAIN[0], DEFAULT_RAIN[1]
    start = int(found.group(1)) - FIRST_NOV_DAY
    end = int(found.group(2)) - FIRST_NOV_DAY if found.group(2) else start + 1
    return (start, end) if 0 <= start <= end <= LAST_DAY else None


def _rain(message: str) -> list[Next]:
    days = _days_of(message)
    if days is None:
        return []
    mm = MM.search(message)
    return [Next(tool="simulate_rain", start_day=days[0], end_day=days[1], mm=float(mm.group(1)) if mm else DEFAULT_RAIN[2]),
            Next(tool="set_day", day=days[0]),
            Next(tool="open_tab", tab="risk"),
            Next(tool="show_toast", text="Plan updated. {moved} works moved out of the rain window.")]


def plan(message: str) -> list[Next]:
    work = ID.search(message)
    work_id = work.group(0).upper() if work else None
    days = DAYS.search(message)
    if WHAT_IF.search(message) and work_id and days:
        return [Next(tool="what_if", work_id=work_id, days=int(days.group(1)))]
    if RAIN.search(message) and not WHY.search(message):
        return _rain(message)
    road = ROAD.search(message)
    if road:
        return [Next(tool="list_works", road=road.group(0)), Next(tool="open_tab", tab="works"),
                Next(tool="select_work", work_id="{first}"), Next(tool="fit_work", work_id="{first}")]
    if work_id:
        return [Next(tool="explain", work_id=work_id), Next(tool="open_drawer", work_id=work_id)]
    date = DATE.search(message)
    if date:
        return [Next(tool="set_day", day=int(date.group(1)) - FIRST_NOV_DAY)]
    return []
