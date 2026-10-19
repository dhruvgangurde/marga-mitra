"""The copilot's steps: reads from the city API, a rain simulation, and moves on the screen. Each returns one result line."""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from agents.department import DEPT_NAMES
from agents.tools import days_label
from contracts import costs
from contracts.interfaces import Emit
from contracts.models import CopilotStep, Scenario, UiAction, WsEvent

Tool = Literal["list_works", "plan_metrics", "risk", "simulate_rain", "replan", "explain", "what_if", "select_work",
               "set_day", "open_tab", "fit_work", "toggle_old_way", "open_drawer", "show_toast", "finish"]

# shortcut: every test case starts on 2 Nov 2026; read the start from the API if that changes
CAL = Scenario(seed=0, start_date=date(2026, 11, 2), segments=[], works=[])
LAST_DAY = 27
RUN_POLL_S = 1.0
RUN_WAIT_S = 60.0
WORK_ID = re.compile(r"^[A-Z]-\d{3}$")
STILL_WORKING = "The new plan is still being made. It will show up for approval."
NOT_MADE = "The new plan could not be made."


class Next(BaseModel):
    # a plain model, like Pick, so both providers accept the schema
    tool: Tool
    work_id: str | None = None
    road: str | None = None
    dept: str | None = None
    text: str | None = None
    start_day: int | None = None
    end_day: int | None = None
    days: int | None = None
    day: int | None = None
    mm: float | None = None
    on: bool | None = None
    tab: Literal["negotiation", "works", "risk", "approvals"] | None = None


class ToolError(Exception):
    pass


@dataclass
class Turn:
    reply_id: str
    emit: Emit
    client: httpx.AsyncClient
    plan_id: str | None
    steps: list[CopilotStep] = field(default_factory=list)
    actions: list[UiAction] = field(default_factory=list)
    results: list[str] = field(default_factory=list)
    last_ids: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    summary: str = ""
    calls: int = 0
    map_shown: bool = False
    failed: bool = False


async def step(t: Turn, text: str, detail: str | None = None, status: str = "done", step_id: str | None = None) -> str:
    sid = step_id or f"{t.reply_id}-S{len(t.steps) + 1}"
    s = CopilotStep(step_id=sid, text=text, detail=detail, status=status)
    for i, old in enumerate(t.steps):
        if old.step_id == sid:
            t.steps[i] = s
            break
    else:
        t.steps.append(s)
    await t.emit(WsEvent(type="copilot.step", data={**s.model_dump(mode="json"), "reply_id": t.reply_id},
                         ts=datetime.now(UTC)))
    return sid


async def act(t: Turn, action: str, **args: Any) -> None:
    ui = UiAction(action=action, args=args)
    t.actions.append(ui)
    await t.emit(WsEvent(type="ui.action", data={**ui.model_dump(mode="json"), "reply_id": t.reply_id},
                         ts=datetime.now(UTC)))


async def get_json(t: Turn, path: str, **params: Any) -> Any:
    try:
        r = await t.client.get(path, params={k: v for k, v in params.items() if v is not None} or None)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ToolError(path) from e


async def post_json(t: Turn, path: str, body: dict[str, Any]) -> Any:
    try:
        r = await t.client.post(path, json=body)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ToolError(path) from e


def _skip(name: str, missing: str) -> str:
    return f"skipped: {name} needs {missing}"


def _news(t: Turn, text: str, *, only_if_empty: bool = False) -> None:
    if not (only_if_empty and t.summary):
        t.summary = text


async def active_plan(t: Turn) -> str | None:
    if t.plan_id:
        return t.plan_id
    plans = await get_json(t, "/plans")  # newest first
    for wanted in ("approved", "waiting_approval"):
        found = next((p for p in plans if p["status"] == wanted), None)
        if found:
            return str(found["plan_id"])
    naive = next((p for p in plans if p["variant"] == "naive"), None)
    return str(naive["plan_id"]) if naive else None


def _days_of(view: dict[str, Any]) -> str | None:
    a = view.get("assignment")
    return days_label(CAL, a["start_day"], a["end_day"]) if a else None


def _kept(view: dict[str, Any], n: Next) -> bool:
    work, a = view["work"], view.get("assignment")
    if n.road and n.road.lower() not in work["road_name"].lower():
        return False
    if n.dept and work["dept"] != n.dept.lower():
        return False
    if n.start_day is not None or n.end_day is not None:
        low, high = n.start_day if n.start_day is not None else 0, n.end_day if n.end_day is not None else 10**6
        return bool(a) and a["start_day"] <= high and a["end_day"] >= low
    return True


def _trench_pair(views: list[dict[str, Any]]) -> str:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for v in views:
        a = v.get("assignment")
        if a and a.get("shared_group"):
            by_group.setdefault(a["shared_group"], []).append(v)
    for pair in by_group.values():
        if len(pair) >= 2:
            first, second = pair[0], pair[1]
            start = min(first["assignment"]["start_day"], second["assignment"]["start_day"])
            end = max(first["assignment"]["end_day"], second["assignment"]["end_day"])
            return (f" {first['work']['work_id']} and {second['work']['work_id']} share one trench on "
                    f"{days_label(CAL, start, end)}.")
    return ""


async def list_works(t: Turn, n: Next) -> str:
    text = (f"Finding works on {n.road}" if n.road
            else f"Finding {DEPT_NAMES[n.dept.lower()]} works" if n.dept and n.dept.lower() in DEPT_NAMES
            else "Finding works")
    sid = await step(t, text, status="running")
    views = [v for v in await get_json(t, "/works", plan_id=t.plan_id) if _kept(v, n)]
    t.last_ids = [v["work"]["work_id"] for v in views]
    await step(t, text, ", ".join(t.last_ids) or "None found", step_id=sid)
    place = f" on {n.road}" if n.road else ""
    if views:
        count = f"{len(views)} works are" if len(views) > 1 else "1 work is"
        _news(t, f"{count} planned{place}.{_trench_pair(views)}")
    else:
        _news(t, f"No works are planned{place}.")
    listed = "; ".join(f"{v['work']['work_id']} {v['work']['title']}, {v['work']['road_name']}, "
                       f"{_days_of(v) or 'not planned'}" for v in views)
    return f"Works: {listed or 'none'}"


async def plan_metrics(t: Turn, n: Next) -> str:
    plan_id = await active_plan(t)
    if plan_id is None:
        return _skip("plan_metrics", "a plan")
    sid = await step(t, "Reading the plan's numbers", status="running")
    m = await get_json(t, f"/plan/{plan_id}/metrics")
    line = (f"Digs per road {m['digs_per_road']:.1f} · clashes {m['clashes']} · "
            f"trench-hours in rain {m['trench_hours_in_rain']:g}")
    await step(t, "Reading the plan's numbers", line, step_id=sid)
    _news(t, f"{line}.", only_if_empty=True)
    return "Metrics: " + ", ".join(f"{k}={v}" for k, v in m.items())


async def risk(t: Turn, n: Next) -> str:
    sid = await step(t, "Reading the forecasts", status="running")
    windows = await get_json(t, "/risk/windows")
    detail = "; ".join(w["label"] for w in windows) or "No heavy rain, poor air or events ahead"
    await step(t, "Reading the forecasts", detail, step_id=sid)
    _news(t, f"{detail}.", only_if_empty=True)
    return "Forecasts: " + ("; ".join(f"{w['label']} ({w['kind']}, {w['value']:g})" for w in windows) or "none")


async def explain(t: Turn, n: Next) -> str:
    if not n.work_id:
        return _skip("explain", "work_id")
    text = f"Reading why {n.work_id} has these dates"
    sid = await step(t, text, status="running")
    reasons = (await get_json(t, f"/explain/{n.work_id}"))["reasons"]
    await step(t, text, reasons[0]["lead"] if reasons else None, step_id=sid)
    if reasons:
        _news(t, f"{reasons[0]['lead']} {reasons[0]['text']}")
    return "Reasons: " + "; ".join(f"{r['lead']} {r['text']}" for r in reasons)


async def what_if(t: Turn, n: Next) -> str:
    if not n.work_id:
        return _skip("what_if", "work_id")
    if n.days is None:
        return _skip("what_if", "days")
    text = f"Trying {n.work_id} {n.days} days later"
    sid = await step(t, text, status="running")
    out = await post_json(t, "/plan/whatif", {"work_id": n.work_id, "delay_days": n.days})
    diff = out["diff"]
    total = sum(c["cost_delta_inr"] for c in diff)
    await step(t, text, f"{len(diff)} works move · nothing is saved", step_id=sid)
    _news(t, f"If {n.work_id} starts {n.days} days later, {len(diff)} works move and the cost goes "
             f"{'up' if total >= 0 else 'down'} by {costs.inr(abs(total))}. Nothing is saved.")
    return "Moved: " + (", ".join(c["work_id"] for c in diff) or "none")


async def wait_run(t: Turn, run_id: str) -> dict[str, Any]:
    """Ask for the run until it stops running or RUN_WAIT_S has passed; returns the last answer."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + RUN_WAIT_S
    run = await get_json(t, f"/runs/{run_id}")
    while run["status"] == "running" and loop.time() < deadline:
        await asyncio.sleep(RUN_POLL_S)
        run = await get_json(t, f"/runs/{run_id}")
    return run


async def _run_outcome(t: Turn, sid: str, text: str, run: dict[str, Any]) -> bool:
    """Close the 'making the plan' step when the run is not ready. Returns True when the copilot must stop."""
    if run["status"] == "running":
        await step(t, text, "Still working", "waiting", sid)
        _news(t, STILL_WORKING)
        return True
    if run["status"] in ("failed", "rejected"):
        await step(t, text, NOT_MADE, "needs", sid)
        _news(t, NOT_MADE)
        t.failed = True
        return True
    return False


async def _approval_step(t: Turn, status: str) -> str:
    if status == "approved":
        await step(t, "Approved, no sign-off needed")
        return "in force"
    await step(t, "Waiting for your approval", status="needs")
    return "waiting for your approval"


def _trench_words(hours: float) -> str:
    return "0 trenches open in the rain" if hours == 0 else f"{hours:g} trench-hours still in the rain"


async def simulate_rain(t: Turn, n: Next) -> str:
    start = 12 if n.start_day is None else n.start_day
    end = 13 if n.end_day is None else n.end_day
    mm = 70.0 if n.mm is None else n.mm
    days = days_label(CAL, start, end)
    reading = f"Reading the rain forecast for {days}"
    a = await step(t, reading, status="running")
    started = await post_json(t, "/risk/forecast-override", {"kind": "rain", "start_day": start, "end_day": end,
                                                              "value": mm, "label": f"Heavy rain, {days}"})
    await step(t, reading, f"{mm:g} mm in 24 hours · simulated", step_id=a)
    finding = "Finding works on low-lying roads"
    b = await step(t, finding, status="running")
    run = await wait_run(t, started["run_id"])
    if await _run_outcome(t, b, finding, run):
        return "The rain was simulated but the new plan is not ready."
    plan_id = run["plan_id"]
    base = (await get_json(t, f"/plan/{plan_id}")).get("base_plan_id") or "naive"
    t.moved = [c["work_id"] for c in await get_json(t, f"/plan/{plan_id}/diff", against=base)]
    await step(t, finding, ", ".join(t.moved) or "None", step_id=b)
    asking = "Asking the departments to move"
    c = await step(t, asking, status="running")
    messages = await get_json(t, "/negotiation", run_id=started["run_id"])
    accepts = [m for m in messages if m["type"] == "ACCEPT"]
    agreed = [w for w in t.moved if any(w in m["work_ids"] for m in accepts)]
    if not t.moved:
        detail = "No works needed to move"
    elif len(agreed) == len(t.moved):
        detail = f"All {len(agreed)} agreed in round {max(m['round'] for m in accepts)}"
    else:
        detail = f"{len(agreed)} of {len(t.moved)} agreed; the scheduler decided the rest"
    await step(t, asking, detail, step_id=c)
    planning = "Re-planning with the scheduler"
    d = await step(t, planning, status="running")
    hours = (await get_json(t, f"/plan/{plan_id}/metrics"))["trench_hours_in_rain"]
    await step(t, planning, _trench_words(hours), step_id=d)
    state = await _approval_step(t, run["status"])
    _news(t, f"Rain is coming on {days}. {len(t.moved)} works moved out of it; the new plan is {state}.")
    return f"Plan {plan_id}; moved: {', '.join(t.moved) or 'none'}; trench-hours in rain: {hours:g}"


async def replan(t: Turn, n: Next) -> str:
    started = await post_json(t, "/plan/orchestrate", {})
    making = "Making a new plan"
    a = await step(t, making, status="running")
    run = await wait_run(t, started["run_id"])
    if await _run_outcome(t, a, making, run):
        return "The new plan is not ready."
    await step(t, making, step_id=a)
    plan_id = run["plan_id"]
    planning = "Re-planning with the scheduler"
    b = await step(t, planning, status="running")
    m = await get_json(t, f"/plan/{plan_id}/metrics")
    await step(t, planning, f"Digs per road {m['digs_per_road']:.1f} · clashes {m['clashes']}", step_id=b)
    state = await _approval_step(t, run["status"])
    _news(t, f"The new plan is {state}.")
    return f"Plan {plan_id}; digs per road {m['digs_per_road']:.1f}; clashes {m['clashes']}"


def _fill(t: Turn, value: str | None) -> str | None:
    """Put the first work found and the count of moved works into a placeholder; None when there is nothing to put."""
    if value is None:
        return None
    if "{first}" in value:
        if not t.last_ids:
            return None
        value = value.replace("{first}", t.last_ids[0])
    if "{moved}" in value:
        if not t.moved:
            return None
        value = value.replace("{moved}", str(len(t.moved)))
    return value


async def _show_map(t: Turn) -> None:
    if t.last_ids and not t.map_shown:
        t.map_shown = True
        await step(t, "Showing them on the map")


def _work_id(t: Turn, n: Next) -> str | None:
    work_id = _fill(t, n.work_id)
    return work_id if work_id and WORK_ID.match(work_id) else None


async def select_work(t: Turn, n: Next) -> str:
    work_id = _work_id(t, n)
    if work_id is None:
        return _skip("select_work", "a work id")
    await _show_map(t)
    await act(t, "select_work", work_id=work_id)
    return f"Selected {work_id}"


async def fit_work(t: Turn, n: Next) -> str:
    work_id = _work_id(t, n)
    if work_id is None:
        return _skip("fit_work", "a work id")
    await _show_map(t)
    await act(t, "fit_work", work_id=work_id)
    return f"Fitted the map to {work_id}"


async def open_drawer(t: Turn, n: Next) -> str:
    work_id = _work_id(t, n)
    if work_id is None:
        return _skip("open_drawer", "a work id")
    await step(t, f"Opening {work_id}")
    await act(t, "open_drawer", work_id=work_id)
    _news(t, f"Here is {work_id}.", only_if_empty=True)
    return f"Opened {work_id}"


async def set_day(t: Turn, n: Next) -> str:
    if n.day is None or not 0 <= n.day <= LAST_DAY:
        return _skip("set_day", "a day from 0 to 27")
    await act(t, "set_day", day=n.day)
    _news(t, f"Showing {days_label(CAL, n.day, n.day)}.", only_if_empty=True)
    return f"Moved the timeline to {days_label(CAL, n.day, n.day)}"


async def open_tab(t: Turn, n: Next) -> str:
    if n.tab is None:
        return _skip("open_tab", "a tab")
    await act(t, "open_tab", tab=n.tab)
    return f"Opened the {n.tab} tab"


async def toggle_old_way(t: Turn, n: Next) -> str:
    if n.on is None:
        return _skip("toggle_old_way", "on or off")
    await act(t, "toggle_old_way", on=n.on)
    return f"Old way {'on' if n.on else 'off'}"


async def show_toast(t: Turn, n: Next) -> str:
    # a number may come only from a placeholder, never from the text itself
    if not n.text or any(ch.isdigit() for ch in n.text):
        return _skip("show_toast", "text without numbers")
    text = _fill(t, n.text)
    if text is None:
        return _skip("show_toast", "something to fill in")
    await act(t, "show_toast", text=text)
    return f"Showed: {text}"


TOOLS: dict[str, Callable[[Turn, Next], Awaitable[str]]] = {
    "list_works": list_works, "plan_metrics": plan_metrics, "risk": risk, "simulate_rain": simulate_rain,
    "replan": replan, "explain": explain, "what_if": what_if, "select_work": select_work, "set_day": set_day,
    "open_tab": open_tab, "fit_work": fit_work, "toggle_old_way": toggle_old_way, "open_drawer": open_drawer,
    "show_toast": show_toast,
}
