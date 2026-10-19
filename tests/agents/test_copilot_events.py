import httpx

from agents.copilot_tools import Turn, act, step
from contracts.models import UiAction


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)


def make_turn(emit):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})), base_url="http://api")
    return Turn(reply_id="CP-1", emit=emit, client=client, plan_id=None)


async def test_a_step_is_replaced_not_duplicated():
    emit = Recorder()
    t = make_turn(emit)
    sid = await step(t, "Finding works", status="running")
    assert sid == "CP-1-S1"
    await step(t, "Finding works", "W-001", step_id=sid)
    assert len(t.steps) == 1
    assert t.steps[0].status == "done"
    assert t.steps[0].detail == "W-001"
    assert [e.type for e in emit.events] == ["copilot.step", "copilot.step"]
    assert all(e.data["reply_id"] == "CP-1" for e in emit.events)


async def test_a_new_step_gets_the_next_id():
    t = make_turn(Recorder())
    await step(t, "One")
    assert await step(t, "Two") == "CP-1-S2"


async def test_a_screen_action_is_stored_and_sent():
    emit = Recorder()
    t = make_turn(emit)
    await act(t, "set_day", day=12)
    assert t.actions == [UiAction(action="set_day", args={"day": 12})]
    event = emit.events[0]
    assert event.type == "ui.action"
    assert event.data["action"] == "set_day"
    assert event.data["args"] == {"day": 12}
    assert event.data["reply_id"] == "CP-1"
