"""Risk windows: heavy rain, poor air and events, from the forecast."""

import argparse
from datetime import date, timedelta

from contracts import costs
from contracts.models import RiskKind, RiskWindow, Scenario
from risk import aqi, weather


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
    # In live mode the hand-made days never mix into the windows, so a fixture window in live mode means the live forecast failed. The command centre shows this.
    live_rain = any(d.rain_live for d in days)
    live_air = any(d.air_live for d in days)
    rain_flags = [d.rain_mm >= heavy and (d.rain_live or not live_rain) for d in days]
    air_flags = [d.aqi >= poor and (d.air_live or not live_air) for d in days]

    for i, (a, b) in enumerate(_runs(rain_flags), start=1):
        found.append(RiskWindow(
            window_id=f"R{i}", kind=RiskKind.rain, start_day=a, end_day=b, segment_ids=list(low_ids),
            value=round(max(d.rain_mm for d in days[a:b + 1]), 1),
            source="open-meteo" if days[a].rain_live else "fixture",
            label=f"Heavy rain, {days_label(start, a, b)}"))

    for i, (a, b) in enumerate(_runs(air_flags), start=1):
        found.append(RiskWindow(
            window_id=f"A{i}", kind=RiskKind.air, start_day=a, end_day=b, segment_ids=list(all_ids),
            value=float(max(d.aqi for d in days[a:b + 1])),
            source="open-meteo" if days[a].air_live else "fixture",
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


def daily_summary(scenario: Scenario, mode: str, start_day: int, end_day: int) -> dict:
    """Highest rain and air quality in a range of days (forecast only, clamped to the horizon)."""
    days = weather.daily_weather(mode)[: scenario.horizon_days]
    chosen = [d for d in days if start_day <= d.day <= end_day]
    max_aqi = max(d.aqi for d in chosen)
    return {"max_rain_mm": max(d.rain_mm for d in chosen), "max_aqi": max_aqi, "band": aqi.band(max_aqi)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Show the risk windows for a test case.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    args = parser.parse_args(argv)

    from data.demo import demo_scenario  # data is only used by the command line
    from data.scenario import generate_scenario

    scenario = demo_scenario() if args.seed == 1 else generate_scenario(args.seed)
    windows = compute_risk_windows(scenario, args.mode)
    print(f"Risk windows · test case {args.seed} · {args.mode}")
    status = weather.live_status()
    if status["source"] == "open-meteo":
        print(f"Forecast source: Open-Meteo, fetched {status['fetched_at']}")
    elif status["error"]:
        print(f"Forecast source: demo forecast (live forecast unavailable: {status['error']})")
    else:
        print("Forecast source: demo forecast")
    for w in windows:
        value = {"rain": f"{w.value:.1f} mm", "air": f"AQI {w.value:.0f}"}.get(w.kind.value, "")
        when = days_label(scenario.start_date, w.start_day, w.end_day)
        print(f"{w.window_id}  {w.kind.value}  {when}  {value}  {len(w.segment_ids)} road segments  {w.source}")
    today = weather.today_day()
    last = today + 5
    s = daily_summary(scenario, args.mode, today, last)
    print(f"Forecast for {days_label(scenario.start_date, today, last)}: highest rain {s['max_rain_mm']:.1f} mm "
          f"in 24 hours · AQI {s['max_aqi']} · {s['band']}")


if __name__ == "__main__":
    main()
