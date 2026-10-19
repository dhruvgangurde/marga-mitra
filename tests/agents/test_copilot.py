import itertools

import httpx
import pytest

from agents import copilot, copilot_tools
from agents.copilot import run_copilot, user_text
from agents.copilot_rules import HELP
from agents.copilot_tools import Next

MUNCHUR = "Show every dig on Munchur Road next week"
RAIN = "Rain is coming on 14 Nov. Re-plan and show me what moved."
TOAST = "Plan updated. 3 works moved out of the rain window."
MUNCHUR_SUMMARY = "4 works are planned on Munchur Road. W-104 and T-221 share one trench on 10–15 Nov."


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)


class FakeLLM:
    provider = "fake"

    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        self.asked.append(user)
        return self.answers.pop(0) if self.answers else None


class Forever(FakeLLM):
    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        self.asked.append(user)
        return Next(tool="risk")


@pytest.fixture
def city(kit, monkeypatch):
    routes = {
        ("GET", "/works"): kit.demo_views(),
        ("GET", "/plans"): [{"plan_id": "P-0007", "status": "approved", "variant": "orchestrated"}],
        ("GET", "/plan/P-0007/metrics"): kit.metrics_json("P-0007"),
        ("GET", "/risk/windows"): [],
        **kit.rain_routes(),
    }
    api = kit.FakeApi(routes)
    monkeypatch.setattr(copilot, "_client", lambda base: api.client())
    monkeypatch.setattr(copilot, "_reply_ids", itertools.count(1))
    monkeypatch.setattr(copilot_tools, "RUN_POLL_S", 0.01)
    return api


def with_model(monkeypatch, llm):
    monkeypatch.setattr(copilot, "get_llm", lambda: llm)


async def ask(message, context=None):
    emit = Recorder()
    reply = await run_copilot(message, context or {"day": 8, "tab": "negotiation"}, "http://api", emit)
    return reply, emit


def actions(reply):
    return [(a.action, a.args) for a in reply.actions]


async def test_the_rain_question_without_a_model(city):
    reply, emit = await ask(RAIN)
    assert [s.text for s in reply.steps] == [
        "Reading the rain forecast for 14–15 Nov", "Finding works on low-lying roads", "Asking the departments to move",
        "Re-planning with the scheduler", "Waiting for your approval"]
    assert actions(reply) == [("set_day", {"day": 12}), ("open_tab", {"tab": "risk"}), ("show_toast", {"text": TOAST})]
    assert reply.text == "Rain is coming on 14–15 Nov. 3 works moved out of it; the new plan is waiting for your approval."
    assert reply.used_llm is False
    assert reply.reply_id == "CP-1"
    assert emit.events
    assert {e.data["reply_id"] for e in emit.events} == {"CP-1"}


async def test_the_munchur_question_without_a_model(city):
    reply, _ = await ask(MUNCHUR)
    assert [(s.text, s.detail) for s in reply.steps] == [
        ("Finding works on Munchur Road", "W-104, T-221, G-310, R-501"), ("Showing them on the map", None)]
    assert actions(reply) == [("open_tab", {"tab": "works"}), ("select_work", {"work_id": "W-104"}),
                              ("fit_work", {"work_id": "W-104"})]
    assert reply.text == MUNCHUR_SUMMARY


async def test_hello_gets_the_help_text(city):
    reply, emit = await ask("Hello")
    assert (reply.steps, reply.actions, reply.text) == ([], [], HELP)
    assert emit.events == []
    assert city.requests == []


async def test_a_model_chooses_the_steps(city, monkeypatch):
    llm = FakeLLM([Next(tool="list_works", road="Munchur Road"), Next(tool="plan_metrics"),
                   Next(tool="select_work", work_id="W-104"), Next(tool="finish", text="Here they are on the map.")])
    with_model(monkeypatch, llm)
    reply, emit = await ask(MUNCHUR)
    assert city.calls == ["GET /works", "GET /plans", "GET /plan/P-0007/metrics"]
    assert reply.text == "Here they are on the map."
    assert reply.used_llm is True
    assert {e.data["reply_id"] for e in emit.events} == {"CP-1"}
    assert "1. Works: W-104" in llm.asked[2]
    assert llm.asked[0].startswith(f"Request: {MUNCHUR}\nScreen: 10 Nov, tab negotiation, selected none\n"
                                   "Done so far: nothing yet\n")


async def test_a_closing_sentence_with_a_number_is_not_used(city, monkeypatch):
    llm = FakeLLM([Next(tool="list_works", road="Munchur Road"), Next(tool="plan_metrics"),
                   Next(tool="select_work", work_id="W-104"), Next(tool="finish", text="There are 4 works")])
    with_model(monkeypatch, llm)
    reply, _ = await ask(MUNCHUR)
    assert reply.text == MUNCHUR_SUMMARY


async def test_a_long_closing_sentence_is_not_used(city, monkeypatch):
    with_model(monkeypatch, FakeLLM([Next(tool="list_works", road="Munchur Road"),
                                     Next(tool="finish", text="word " * 60)]))
    reply, _ = await ask(MUNCHUR)
    assert reply.text == MUNCHUR_SUMMARY


async def test_the_copilot_stops_after_six_steps(city, monkeypatch):
    with_model(monkeypatch, Forever([]))
    reply, _ = await ask("What is ahead?")
    assert city.calls == ["GET /risk/windows"] * 6
    assert reply.text.startswith("I stopped after 6 steps.")


async def test_no_model_answer_at_all_falls_back_to_the_rules(city, monkeypatch):
    with_model(monkeypatch, FakeLLM([]))
    reply, _ = await ask(MUNCHUR)
    assert reply.used_llm is False
    assert reply.text == MUNCHUR_SUMMARY


async def test_a_silent_model_later_just_stops(city, monkeypatch):
    with_model(monkeypatch, FakeLLM([Next(tool="list_works", road="Munchur Road")]))
    reply, _ = await ask(MUNCHUR)
    assert reply.used_llm is True
    assert reply.text == MUNCHUR_SUMMARY
    assert len(reply.steps) == 1


async def test_an_unreachable_service_is_reported_not_raised(kit, monkeypatch):
    api = kit.FakeApi({("GET", "/works"): httpx.Response(500, json={"detail": "down"})})
    monkeypatch.setattr(copilot, "_client", lambda base: api.client())
    monkeypatch.setattr(copilot, "_reply_ids", itertools.count(1))
    reply, _ = await ask(MUNCHUR)
    assert [(s.text, s.detail, s.status) for s in reply.steps] == [
        ("Finding works on Munchur Road", "The plan service did not answer. Try again.", "needs")]
    assert reply.text == "I could not finish: the plan service did not answer."


async def test_a_model_answer_still_counts_when_the_service_then_fails(kit, monkeypatch):
    api = kit.FakeApi({})
    monkeypatch.setattr(copilot, "_client", lambda base: api.client())
    with_model(monkeypatch, FakeLLM([Next(tool="list_works", road="Munchur Road")]))
    reply, _ = await ask(MUNCHUR)
    assert reply.text == "I could not finish: the plan service did not answer."
    assert reply.used_llm is True


async def test_a_failed_plan_stops_the_story(kit, city, monkeypatch):
    failed = kit.rain_routes(run_status={"run_id": "RUN-0008", "status": "failed"})
    city.routes.update(failed)
    reply, _ = await ask(RAIN)
    assert [a[0] for a in actions(reply)] == []  # the screen is not moved for a plan that was not made
    assert reply.text == "The new plan could not be made."


async def test_the_copilot_sends_the_plan_on_screen(city, monkeypatch):
    with_model(monkeypatch, FakeLLM([Next(tool="list_works"), Next(tool="finish")]))
    await ask("Show everything", {"day": 8, "tab": "works", "selected_work": "W-104", "plan_id": "P-0007"})
    assert city.requests[0][2] == {"plan_id": "P-0007"}


def test_user_text_with_progress():
    text = user_text("Why?", {"day": 12, "tab": "risk", "selected_work": "W-104"}, ["Works: W-104", "Metrics: ok"])
    assert text == ("Request: Why?\nScreen: 14 Nov, tab risk, selected W-104\n"
                    "Done so far:\n1. Works: W-104\n2. Metrics: ok\nChoose the next step.")


def test_user_text_defaults_to_today():
    assert "Screen: 10 Nov, tab negotiation, selected none" in user_text("Hi", {}, [])


def test_the_command_prints_each_step_and_the_reply(city, capsys):
    copilot.main(["--ask", MUNCHUR])
    out = capsys.readouterr().out.splitlines()
    assert sum(ln.startswith("STEP done") for ln in out) == 2
    assert sum(ln.startswith("ACTION") for ln in out) == 3
    assert sum(ln.startswith("REPLY") for ln in out) == 1
    assert "STEP done Finding works on Munchur Road · W-104, T-221, G-310, R-501" in out
    assert "STEP running Finding works on Munchur Road" in out
    assert "ACTION open_tab tab=works" in out
    assert out[-1] == "(rules)"
