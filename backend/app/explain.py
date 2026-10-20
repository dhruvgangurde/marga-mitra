"""The "Why?" drawer: plain reasons and rule checks for a work's dates or a plan. Pure, except forecast_summary."""
from datetime import date, timedelta

from backend.app.deps import day_range
from backend.app.words import clock, date_words, day_label, dept_name, metres
from contracts import costs
from contracts.models import (
    Assignment,
    Dept,
    Metrics,
    Mode,
    NegotiationMessage,
    Plan,
    PlanVariant,
    Reason,
    RiskKind,
    RuleCheck,
    Scenario,
    Work,
)

ICONS = [("Emergency", "siren"), ("Shares one trench", "handshake"), ("protected road", "lock"), ("Trenchless", "road"),
         ("rain", "rain"), ("keep the road free", "flag"), ("Resurfaces", "road"), ("agreed", "handshake"),
         ("As the department asked", "check")]
COUNTS = {2: "two", 3: "three", 4: "four"}
# field, icon, label, how a value is written
METRIC_LINES = [
    ("digs_per_road", "shovel", "Digs per road", lambda v: f"{v:.1f}"),
    ("lane_closure_hours", "car", "Lane-closure hours", lambda v: costs.inr(round(v)).removeprefix("₹")),
    ("trench_hours_in_rain", "rain", "Trench-hours in rain", lambda v: costs.inr(round(v)).removeprefix("₹")),
    ("clashes", "warning", "Clashes", str),
    ("days_late", "clock", "Days late", lambda v: f"{v:.1f}"),
    ("cost_inr", "rupee", "Cost", costs.inr),
]


def icon_for(reason: str) -> str:
    low = reason.lower()
    return next((icon for words, icon in ICONS if words.lower() in low), "clock")


def source_of(m: NegotiationMessage) -> str:
    return f"negotiation, round {m.round}, {clock(m.ts, seconds=True)}"


def days_of(work: Work, a: Assignment | None) -> tuple[int, int, Mode]:
    """The planned days and method, else the ones the department asked for."""
    if a:
        return a.start_day, a.end_day, a.mode
    first = work.modes[0]
    return work.requested_start, work.requested_start + first.duration_days - 1, first.mode


def _protected_until(work: Work, scenario: Scenario, start_day: int) -> date | None:
    """The latest protection date among the work's segments protected on its start date."""
    day = scenario.start_date + timedelta(days=start_day)
    dates = [s.protected_until for s in scenario.segments
             if s.segment_id in work.segment_ids and s.protected_until and s.protected_until >= day]
    return max(dates, default=None)


def _about(messages: list[NegotiationMessage], work_id: str) -> list[NegotiationMessage]:
    return [m for m in messages if work_id in m.work_ids]


def _shares(works: dict[str, Work], a: Assignment, b: Assignment) -> bool:
    return a.work_id != b.work_id and bool(set(works[a.work_id].segment_ids) & set(works[b.work_id].segment_ids))


def _first_reason(work: Work, a: Assignment, plan: Plan, scenario: Scenario, works: dict[str, Work],
                  messages: list[NegotiationMessage], main: str) -> Reason:
    if not a.shared_group:
        method = "trenchless" if a.mode == Mode.trenchless else "open cut"
        return Reason(icon=icon_for(a.reason), lead=a.reason or "Planned by the scheduler.",
                      text=f"Planned for {day_range(scenario.start_date, a.start_day, a.end_day)}, {method}.", source=main)
    group = [works[b.work_id] for b in plan.assignments if b.shared_group == a.shared_group and b.work_id in works]
    others = " and ".join(f"{dept_name(w.dept)} ({w.work_id})" for w in group if w.work_id != work.work_id)
    agreed = [m for m in _about(messages, work.work_id) if m.chosen_option is not None
              and m.chosen_option < len(m.options) and m.options[m.chosen_option].shared_group == a.shared_group]
    shortest = min(w.length_m for w in group)
    return Reason(icon="handshake", lead=f"Shares one trench with {others}.",
                  text=f"One dig instead of {COUNTS.get(len(group), str(len(group)))} on the same {metres(shortest)}.",
                  source=source_of(agreed[-1]) if agreed else main)


def _moved_reason(work: Work, a: Assignment, scenario: Scenario, messages: list[NegotiationMessage],
                  main: str) -> Reason:
    asked = day_label(scenario.start_date, work.requested_start)
    own = [m for m in _about(messages, work.work_id) if m.sender == work.dept.value]
    text, source = ((own[-1].body, source_of(own[-1])) if own
                    else (f"The {dept_name(work.dept)} department asked for {asked}.", main))
    return Reason(icon="clock", lead=f"Starts on {day_label(scenario.start_date, a.start_day)}, not {asked}.",
                  text=text, source=source)


def _order_reason(work: Work, a: Assignment, plan: Plan, scenario: Scenario, works: dict[str, Work]) -> Reason | None:
    live = [b for b in plan.assignments if b.work_id in works and not works[b.work_id].done and _shares(works, a, b)]
    years = costs.policy()["no_dig_days_after_restoration"] // 365
    kept = f"rule: no new digs for {years} years after resurfacing"
    stopped = "The new surface would be cut, so the rules check stops this plan."
    if work.dept == Dept.roads:
        digs = [b for b in live if works[b.work_id].dept != Dept.roads and b.mode == Mode.open_cut]
        if not digs:
            return None
        late = sorted(b.work_id for b in digs if b.end_day >= a.start_day)
        if late:
            return Reason(icon="warning", lead=f"Starts before {', '.join(late)} finish.", text=stopped,
                          source="rule: resurfacing comes after every dig")
        last = max(b.end_day for b in digs)
        return Reason(icon="road", lead=f"Starts after the last dig ends on {day_label(scenario.start_date, last)}.",
                      text=f"{work.road_name} is then protected for {years} years.", source=kept)
    roads = [b for b in live if works[b.work_id].dept == Dept.roads]
    if not roads:
        return None
    r = min(roads, key=lambda b: (b.start_day, b.work_id))
    resurfacing = day_label(scenario.start_date, r.start_day)
    if a.end_day < r.start_day:
        return Reason(icon="road", lead=f"Ends before resurfacing on {resurfacing}.", text="The new surface is never cut.",
                      source=kept)
    if a.mode == Mode.trenchless:  # trenchless never cuts the new surface, so there is no order to explain
        return None
    return Reason(icon="warning", lead=f"Still digging when resurfacing {r.work_id} starts on {resurfacing}.",
                  text=stopped, source="rule: resurfacing comes after every dig")


def work_reasons(work: Work, a: Assignment | None, plan: Plan, scenario: Scenario,
                 messages: list[NegotiationMessage]) -> list[Reason]:
    main = ("the departments' requests" if plan.variant == PlanVariant.naive
            else f"the scheduler, {clock(plan.created_at)}")
    if a is None:
        if work.done:
            return [Reason(icon="check", lead="Already done.", text="It finished before this plan starts.",
                           source="the work list")]
        note = next((n for n in plan.notes if work.work_id in n), "No dates fit every rule.")
        return [Reason(icon="warning", lead="Could not be planned.", text=note, source=main)]
    works = {w.work_id: w for w in scenario.works}
    reasons = [_first_reason(work, a, plan, scenario, works, messages, main)]
    if a.start_day != work.requested_start:
        reasons.append(_moved_reason(work, a, scenario, messages, main))
    until = _protected_until(work, scenario, a.start_day)
    if until:
        text = ("Trenchless only: the new surface is not cut." if a.mode == Mode.trenchless
                else "Emergency digs may cut it; they are reviewed after." if work.is_emergency
                else "An open cut here breaks the rules.")
        reasons.append(Reason(icon="lock", lead=f"{work.road_name} is protected until {date_words(until)}.", text=text,
                              source="the protected-road list"))
    order = _order_reason(work, a, plan, scenario, works)
    return reasons + ([order] if order else [])


def _protected_check(work: Work, scenario: Scenario, start: int, mode: Mode) -> RuleCheck:
    until = _protected_until(work, scenario, start)
    road = work.road_name
    if until is None:
        return RuleCheck(name="Road is not protected", severity="ok", detail=f"{road} is not in the protected-road list")
    if mode == Mode.trenchless:
        return RuleCheck(name="Protected road: no open cut", severity="ok",
                         detail=f"{road} is protected until {date_words(until)}; this work is trenchless")
    if work.is_emergency:
        return RuleCheck(name="Emergency dig on a protected road", severity="warn",
                         detail="Allowed at once by the rules and reviewed after")
    return RuleCheck(name="Open cut on a protected road", severity="fail",
                     detail=f"{road} is protected until {date_words(until)}")


def _window_labels(work: Work, scenario: Scenario, kind: RiskKind, start: int, end: int) -> str:
    return "; ".join(w.label for w in scenario.risk_windows if w.kind == kind
                     and set(w.segment_ids) & set(work.segment_ids) and w.start_day <= end and start <= w.end_day)


def work_rules(work: Work, a: Assignment | None, scenario: Scenario, summary: dict | None) -> list[RuleCheck]:
    start, end, mode = days_of(work, a)
    needed = costs.deposit_inr(work.dept, work.length_m, mode)
    deposit = (RuleCheck(name="Deposit held until the repair is verified", severity="ok", detail=costs.inr(work.deposit_inr))
               if work.deposit_inr >= needed else
               RuleCheck(name="Deposit is too small", severity="warn",
                         detail=f"{costs.inr(work.deposit_inr)} held; {costs.inr(needed)} needed for this method"))
    checks = [_protected_check(work, scenario, start, mode), deposit]
    if mode == Mode.trenchless:
        return checks + [RuleCheck(name="No open trench in the rain", severity="ok", detail="Trenchless: the road is not cut"),
                         RuleCheck(name="No dust from this work", severity="ok", detail="Trenchless: no open cut")]
    rain = _window_labels(work, scenario, RiskKind.rain, start, end)
    air = _window_labels(work, scenario, RiskKind.air, start, end)
    dates = day_range(scenario.start_date, start, end)
    checks.append(RuleCheck(name="Heavy rain on this road during the work", severity="warn", detail=rain) if rain else
                  RuleCheck(name=f"No heavy rain forecast for {dates}", severity="ok",
                            detail=f"Highest: {summary['max_rain_mm']:g} mm in 24 hours" if summary
                            else "No heavy-rain window on this road"))
    checks.append(RuleCheck(name="Poor air on open-cut days", severity="warn", detail=air) if air else
                  RuleCheck(name="Air quality is fine for open cuts", severity="ok",
                            detail=f"AQI {summary['max_aqi']} · {summary['band']}" if summary
                            else "No poor-air days in these dates"))
    return checks


def plan_reasons(old: Metrics, new: Metrics, source: str) -> list[Reason]:
    out = []
    for field, icon, label, fmt in METRIC_LINES:
        before, after = getattr(old, field), getattr(new, field)
        if fmt(before) == fmt(after):
            continue
        out.append(Reason(icon=icon, lead=f"{label} {fmt(before)} → {fmt(after)}.",
                          text="Better than before." if after < before else "Worse than before.", source=source))
    return out or [Reason(icon="info", lead="Same numbers as before.",
                          text="No total changes against the plan it replaces.", source=source)]


def forecast_summary(scenario: Scenario, start_day: int, end_day: int) -> dict | None:
    """Highest rain and air quality over these days, or None before the risk track is merged."""
    from backend.app.config import get_settings

    try:
        from risk.windows import daily_summary
    except ImportError:
        return None
    return daily_summary(scenario, get_settings().weather_mode, start_day, end_day)
