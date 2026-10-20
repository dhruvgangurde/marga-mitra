"""How times, days, places and departments are written on screen. India time is the fixed offset +05:30."""
from datetime import date, datetime, timedelta, timezone

from contracts.models import Dept

IST = timezone(timedelta(hours=5, minutes=30))


def clock(dt: datetime, seconds: bool = False) -> str:
    """'09:41', or '10:02:16' with seconds, in India time."""
    return dt.astimezone(IST).strftime("%H:%M:%S" if seconds else "%H:%M")


def day_label(start: date, day: int) -> str:
    """'10 Nov' for day index `day` after `start`."""
    d = start + timedelta(days=day)
    return f"{d.day} {d:%b}"


def date_words(d: date) -> str:
    return f"{d.day} {d:%b} {d.year}"


def dept_name(dept: Dept) -> str:
    return dept.value.capitalize()


def metres(m: float) -> str:
    """'620 m'; from 1,000 m on, '1.1 km'."""
    return f"{round(m)} m" if round(m) < 1000 else f"{round(m / 1000, 1):g} km"
