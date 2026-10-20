"""Risk windows: heavy rain, poor air and events, from the forecast."""

from datetime import date, timedelta

from contracts import costs
from contracts.models import RiskKind, RiskWindow, Scenario
from risk import weather


def _fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def days_label(start: date, a: int, b: int) -> str:
    first, last = start + timedelta(days=a), start + timedelta(days=b)
    if a == b:
        return _fmt(first)
    if (first.month, first.year) == (last.month, last.year):
        return f"{first.day}–{_fmt(last)}"
    return f"{_fmt(first)} – {_fmt(last)}"


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    runs, begin = [], None
    for i, flag in enumerate(flags):
        if flag and begin is None:
            begin = i
        if not flag and begin is not None:
            runs.append((begin, i - 1))
            begin = None
    if begin is not None:
        runs.append((begin, len(flags) - 1))
    return runs


def compute_risk_windows(
    scenario: Scenario, mode: str = "fixture", overrides: list[RiskWindow] | None = None
) -> list[RiskWindow]:
    limits = costs.policy()["risk"]
    heavy, poor = limits["heavy_rain_mm_24h"], limits["poor_aqi_threshold"]
    low_ids = [s.segment_id for s in scenario.segments if s.low_lying]
    all_ids = [s.segment_id for s in scenario.segments]
    start = scenario.start_date

    found: list[RiskWindow] = [w for w in scenario.risk_windows if w.kind == RiskKind.event]
    days = weather.daily_weather(mode)[: scenario.horizon_days]

    for i, (a, b) in enumerate(_runs([d.rain_mm >= heavy for d in days]), start=1):
        found.append(RiskWindow(
            window_id=f"R{i}", kind=RiskKind.rain, start_day=a, end_day=b, segment_ids=list(low_ids),
            value=round(max(d.rain_mm for d in days[a:b + 1]), 1), source=days[a].source,
            label=f"Heavy rain, {days_label(start, a, b)}"))

    for i, (a, b) in enumerate(_runs([d.aqi >= poor for d in days]), start=1):
        found.append(RiskWindow(
            window_id=f"A{i}", kind=RiskKind.air, start_day=a, end_day=b, segment_ids=list(all_ids),
            value=float(max(d.aqi for d in days[a:b + 1])), source=days[a].source,
            label=f"Poor air, {days_label(start, a, b)}"))

    for w in overrides or []:
        if not w.segment_ids and w.kind == RiskKind.rain:
            w = w.model_copy(update={"segment_ids": list(low_ids)})
        elif not w.segment_ids and w.kind == RiskKind.air:
            w = w.model_copy(update={"segment_ids": list(all_ids)})
        found.append(w)

    seen: set[str] = set()
    unique = []
    for w in found:
        if w.window_id not in seen:
            seen.add(w.window_id)
            unique.append(w)
    return sorted(unique, key=lambda w: (w.start_day, w.end_day, w.window_id))
