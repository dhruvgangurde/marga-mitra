import json
from typing import get_args

import pytest

from agents import copilot_tools
from agents.copilot_tools import (
    TOOLS,
    Next,
    Turn,
    active_plan,
    explain,
    fit_work,
    list_works,
    open_drawer,
    risk,
    select_work,
    set_day,
    show_toast,
    simulate_rain,
    what_if,
)


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)

    def of(self, kind):
        return [e for e in self.events if e.type == kind]


@pytest.fixture
def emit():
    return Recorder()


@pytest.fixture(autouse=True)
def _quick_polling(monkeypatch):
    monkeypatch.setattr(copilot_tools, "RUN_POLL_S", 0.01)
    monkeypatch.setattr(copilot_tools, "RUN_WAIT_S", 0.2)


def turn(api, emit, plan_id=None):
    return Turn(reply_id="CP-1", emit=emit, client=api.client(), plan_id=plan_id)


def seen(t):
    return [(s.text, s.detail, s.status) for s in t.steps]


# ---------- the read steps ----------
async def test_list_works_on_a_road(kit, emit):
    api = kit.FakeApi({("GET", "/works"): kit.tiny_views()})
    t = turn(api, emit)
    result = await list_works(t, Next(tool="list_works", road="test road"))
    assert seen(t) == [("Finding works on test road", "W-001, T-001, G-001, R-001", "done")]
    assert t.summary == "4 works are planned on test road. W-001 and T-001 share one trench on 10–14 Nov."
    assert t.last_ids == ["W-001", "T-001", "G-001", "R-001"]
    assert result.startswith("Works: W-001 Water main, Test Road, 10–14 Nov; T-001")


async def test_list_works_filters_by_department_and_days(kit, emit):
    api = kit.FakeApi({("GET", "/works"): kit.tiny_views()})
    t = turn(api, emit)
    await list_works(t, Next(tool="list_works", dept="Gas"))
    assert seen(t)[0] == ("Finding Gas works", "G-001", "done")
    assert t.summary == "1 work is planned."
    t2 = turn(api, emit)
    await list_works(t2, Next(tool="list_works", start_day=20, end_day=21))
    assert seen(t2) == [("Finding works", "None found", "done")]
    assert t2.summary == "No works are planned."


async def test_list_works_sends_the_plan_id(kit, emit):
    api = kit.FakeApi({("GET", "/works"): kit.tiny_views()})
    await list_works(turn(api, emit, plan_id="P-0007"), Next(tool="list_works"))
    assert api.requests[0][2] == {"plan_id": "P-0007"}


async def test_active_plan_prefers_the_context_then_approved(kit, emit):
    plans = [{"plan_id": "P-3", "status": "waiting_approval", "variant": "orchestrated"},
             {"plan_id": "P-2", "status": "approved", "variant": "orchestrated"},
             {"plan_id": "P-1", "status": "draft", "variant": "naive"}]
    api = kit.FakeApi({("GET", "/plans"): plans})
    assert await active_plan(turn(api, emit, plan_id="P-9")) == "P-9"
    assert api.requests == []
    assert await active_plan(turn(api, emit)) == "P-2"
    assert await active_plan(turn(kit.FakeApi({("GET", "/plans"): [plans[0], plans[2]]}), emit)) == "P-3"
    assert await active_plan(turn(kit.FakeApi({("GET", "/plans"): [plans[2]]}), emit)) == "P-1"
    assert await active_plan(turn(kit.FakeApi({("GET", "/plans"): []}), emit)) is None


async def test_plan_metrics_and_risk(kit, emit):
    api = kit.FakeApi({("GET", "/plan/P-7/metrics"): kit.metrics_json("P-7", rain=0.0, digs=2.04, clashes=1),
                       ("GET", "/risk/windows"): [{"label": "Heavy rain, 14–15 Nov", "kind": "rain", "value": 70.0}]})
    t = turn(api, emit, plan_id="P-7")
    line = await copilot_tools.plan_metrics(t, Next(tool="plan_metrics"))
    assert seen(t)[0] == ("Reading the plan's numbers", "Digs per road 2.0 · clashes 1 · trench-hours in rain 0", "done")
    assert "clashes=1" in line
    assert await risk(t, Next(tool="risk")) == "Forecasts: Heavy rain, 14–15 Nov (rain, 70)"
    assert seen(t)[1] == ("Reading the forecasts", "Heavy rain, 14–15 Nov", "done")
    # reads that only support an answer keep the first news
    assert t.summary == "Digs per road 2.0 · clashes 1 · trench-hours in rain 0."


async def test_plan_metrics_without_a_plan_is_skipped(kit, emit):
    t = turn(kit.FakeApi({("GET", "/plans"): []}), emit)
    assert await copilot_tools.plan_metrics(t, Next(tool="plan_metrics")) == "skipped: plan_metrics needs a plan"
    assert t.steps == []


async def test_risk_with_nothing_ahead(kit, emit):
    t = turn(kit.FakeApi({("GET", "/risk/windows"): []}), emit)
    await risk(t, Next(tool="risk"))
    assert seen(t) == [("Reading the forecasts", "No heavy rain, poor air or events ahead", "done")]


async def test_explain_reads_the_first_reason(kit, emit):
    reasons = [{"icon": "x", "lead": "One trench.", "text": "Water and telecom dig together.", "source": "plan"},
               {"icon": "y", "lead": "After rain.", "text": "The forecast.", "source": "risk"}]
    t = turn(kit.FakeApi({("GET", "/explain/W-104"): {"reasons": reasons}}), emit)
    result = await explain(t, Next(tool="explain", work_id="W-104"))
    assert seen(t) == [("Reading why W-104 has these dates", "One trench.", "done")]
    assert t.summary == "One trench. Water and telecom dig together."
    assert result == "Reasons: One trench. Water and telecom dig together.; After rain. The forecast."


async def test_explain_without_a_work_makes_no_request(kit, emit):
    api = kit.FakeApi({})
    t = turn(api, emit)
    assert await explain(t, Next(tool="explain")) == "skipped: explain needs work_id"
    assert api.requests == []
    assert t.steps == []


async def test_what_if_reports_the_cost_change(kit, emit):
    out = {"plan": {}, "metrics": {}, "diff": [{"work_id": "T-221", "cost_delta_inr": 12000},
                                                {"work_id": "G-310", "cost_delta_inr": -2000}]}
    api = kit.FakeApi({("POST", "/plan/whatif"): out})
    t = turn(api, emit)
    result = await what_if(t, Next(tool="what_if", work_id="T-221", days=2))
    assert json.loads(api.requests[0][3]) == {"work_id": "T-221", "delay_days": 2}
    assert seen(t) == [("Trying T-221 2 days later", "2 works move · nothing is saved", "done")]
    assert t.summary == ("If T-221 starts 2 days later, 2 works move and the cost goes up by ₹10,000. "
                         "Nothing is saved.")
    assert result == "Moved: T-221, G-310"
    assert await what_if(t, Next(tool="what_if", work_id="T-221")) == "skipped: what_if needs days"


# ---------- rain ----------
RAIN_STEPS = [
    ("Reading the rain forecast for 14–15 Nov", "70 mm in 24 hours · simulated", "done"),
    ("Finding works on low-lying roads", "D-412, P-118, W-118", "done"),
    ("Asking the departments to move", "All 3 agreed in round 1", "done"),
    ("Re-planning with the scheduler", "0 trenches open in the rain", "done"),
    ("Waiting for your approval", None, "needs"),
]


async def test_simulate_rain_plays_the_demo_story(kit, emit):
    api = kit.FakeApi(kit.rain_routes())
    t = turn(api, emit)
    result = await simulate_rain(t, Next(tool="simulate_rain"))
    assert seen(t) == RAIN_STEPS
    assert json.loads(api.requests[0][3]) == {"kind": "rain", "start_day": 12, "end_day": 13, "value": 70.0,
                                              "label": "Heavy rain, 14–15 Nov"}
    assert len(emit.of("copilot.step")) == 9
    assert t.moved == ["D-412", "P-118", "W-118"]
    assert t.summary == "Rain is coming on 14–15 Nov. 3 works moved out of it; the new plan is waiting for your approval."
    assert result == "Plan P-0008; moved: D-412, P-118, W-118; trench-hours in rain: 0"
    diff = next(r for r in api.requests if r[1].endswith("/diff"))
    assert diff[2] == {"against": "P-0007"}


async def test_simulate_rain_with_other_days_and_force(kit, emit):
    api = kit.FakeApi(kit.rain_routes())
    t = turn(api, emit)
    await simulate_rain(t, Next(tool="simulate_rain", start_day=18, end_day=19, mm=85))
    assert json.loads(api.requests[0][3]) == {"kind": "rain", "start_day": 18, "end_day": 19, "value": 85.0,
                                              "label": "Heavy rain, 20–21 Nov"}
    assert t.steps[0].detail == "85 mm in 24 hours · simulated"


async def test_a_failed_run_stops_the_story(kit, emit):
    failed = {"run_id": "RUN-0008", "status": "failed"}
    t = turn(kit.FakeApi(kit.rain_routes(run_status=failed)), emit)
    await simulate_rain(t, Next(tool="simulate_rain"))
    assert seen(t)[1] == ("Finding works on low-lying roads", "The new plan could not be made.", "needs")
    assert len(t.steps) == 2
    assert t.failed is True
    assert t.summary == "The new plan could not be made."


async def test_a_slow_run_is_left_waiting(kit, emit):
    running = {"run_id": "RUN-0008", "status": "running"}
    t = turn(kit.FakeApi(kit.rain_routes(run_status=running)), emit)
    await simulate_rain(t, Next(tool="simulate_rain"))
    assert seen(t)[1] == ("Finding works on low-lying roads", "Still working", "waiting")
    assert t.summary == "The new plan is still being made. It will show up for approval."
    assert t.failed is False


async def test_an_approved_run_needs_no_sign_off(kit, emit):
    approved = {"run_id": "RUN-0008", "status": "approved", "plan_id": "P-0008"}
    t = turn(kit.FakeApi(kit.rain_routes(run_status=approved)), emit)
    await simulate_rain(t, Next(tool="simulate_rain"))
    assert seen(t)[-1] == ("Approved, no sign-off needed", None, "done")
    assert t.summary.endswith("the new plan is in force.")


async def test_rain_that_moves_nothing(kit, emit):
    t = turn(kit.FakeApi(kit.rain_routes(moved=())), emit)
    await simulate_rain(t, Next(tool="simulate_rain"))
    assert seen(t)[1][1] == "None"
    assert seen(t)[2][1] == "No works needed to move"


async def test_replan_makes_a_new_plan(kit, emit):
    routes = kit.rain_routes()
    routes[("POST", "/plan/orchestrate")] = routes.pop(("POST", "/risk/forecast-override"))
    t = turn(kit.FakeApi(routes), emit)
    result = await copilot_tools.replan(t, Next(tool="replan"))
    assert seen(t) == [("Making a new plan", None, "done"),
                       ("Re-planning with the scheduler", "Digs per road 2.0 · clashes 0", "done"),
                       ("Waiting for your approval", None, "needs")]
    assert t.summary == "The new plan is waiting for your approval."
    assert result == "Plan P-0008; digs per road 2.0; clashes 0"


# ---------- the screen ----------
async def test_the_toast_counts_the_moved_works(kit, emit):
    t = turn(kit.FakeApi(kit.rain_routes()), emit)
    await simulate_rain(t, Next(tool="simulate_rain"))
    await show_toast(t, Next(tool="show_toast", text="Plan updated. {moved} works moved out of the rain window."))
    assert t.actions[-1].args == {"text": "Plan updated. 3 works moved out of the rain window."}
    before = len(t.actions)
    assert (await show_toast(t, Next(tool="show_toast", text="3 works moved"))).startswith("skipped")
    assert len(t.actions) == before


async def test_the_first_work_found_is_selected_and_the_map_shown_once(kit, emit):
    t = turn(kit.FakeApi({("GET", "/works"): kit.tiny_views()}), emit)
    await list_works(t, Next(tool="list_works", road="test road"))
    await select_work(t, Next(tool="select_work", work_id="{first}"))
    await fit_work(t, Next(tool="fit_work", work_id="{first}"))
    assert [(a.action, a.args) for a in t.actions] == [("select_work", {"work_id": "W-001"}),
                                                       ("fit_work", {"work_id": "W-001"})]
    assert [s.text for s in t.steps].count("Showing them on the map") == 1


async def test_a_placeholder_with_nothing_to_fill_is_skipped(kit, emit):
    t = turn(kit.FakeApi({}), emit)
    assert (await select_work(t, Next(tool="select_work", work_id="{first}"))).startswith("skipped")
    assert (await open_drawer(t, Next(tool="open_drawer", work_id="not a work"))).startswith("skipped")
    assert (await show_toast(t, Next(tool="show_toast", text="{moved} moved"))).startswith("skipped")
    assert t.actions == []


async def test_set_day_stays_inside_the_horizon(kit, emit):
    t = turn(kit.FakeApi({}), emit)
    assert (await set_day(t, Next(tool="set_day", day=28))).startswith("skipped")
    assert (await set_day(t, Next(tool="set_day", day=-1))).startswith("skipped")
    await set_day(t, Next(tool="set_day", day=12))
    assert t.actions[0].args == {"day": 12}
    assert t.summary == "Showing 14 Nov."


async def test_open_drawer_names_the_work(kit, emit):
    t = turn(kit.FakeApi({}), emit)
    await open_drawer(t, Next(tool="open_drawer", work_id="W-104"))
    assert t.steps[0].text == "Opening W-104"
    assert t.summary == "Here is W-104."


def test_every_tool_but_finish_has_a_step():
    assert set(TOOLS) == set(get_args(copilot_tools.Tool)) - {"finish"}
