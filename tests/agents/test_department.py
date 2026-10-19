import pytest

from agents.conflicts import detect_conflicts
from agents.department import PROMPTS, DepartmentAgent, Pick, system_prompt
from agents.fallback import choose
from agents.llm import NoLLM
from agents.tools import options_for
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import Dept, MessageType, Mode, NegotiationOption


def opt(cost: int, label: str = "A · x") -> NegotiationOption:
    return NegotiationOption(label=label, work_id="W-001", start_day=0, mode=Mode.open_cut, cost_delta_inr=cost)


def test_choose_nothing():
    assert choose([]) == -1


def test_choose_the_cheapest():
    assert choose([opt(10000), opt(-336000), opt(0)]) == 1


def test_choose_ties_go_to_the_lower_index():
    assert choose([opt(5), opt(0), opt(0)]) == 1


@pytest.mark.parametrize("dept", list(Dept))
def test_every_department_has_a_prompt(dept):
    assert (PROMPTS / f"{dept.value}.md").exists()
    text = system_prompt(dept)
    assert f"{dept.value.capitalize()} department" in text
    assert "Choose only among the numbered options" in text


def test_every_department_is_told_to_answer_at_once():
    for dept in Dept:
        assert "Answer at once" in system_prompt(dept)


def test_water_only_fears_rain_when_the_notes_name_it():
    text = system_prompt(Dept.water)
    assert "When the notes mention heavy rain" in text
    assert "finishing before the rain is the safer choice" in text


def test_every_department_leaves_rain_events_and_protected_roads_to_the_notes():
    for dept in Dept:
        assert "matter only when the clash notes mention them" in system_prompt(dept)


def test_every_department_is_told_to_write_no_digit():
    for dept in Dept:
        assert "Write no digit at all" in system_prompt(dept)


class FakeLLM:
    provider = "fake"

    def __init__(self, pick: Pick | None):
        self.pick = pick
        self.calls: list[tuple[str, str]] = []

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        self.calls.append((system, user))
        return self.pick


@pytest.fixture
def world():
    s = tiny_scenario()
    p = fake_naive_plan(s)
    c4 = next(c for c in detect_conflicts(s, p) if c.conflict_id == "C4")
    return s, p, c4, options_for(c4, s, p, "W-001")


async def ask(llm, world, options=None):
    s, p, c4, opts = world
    agent = DepartmentAgent(Dept.water, llm)
    return await agent.respond(c4, "W-001", opts if options is None else options, s, p, "RUN-1", 1, "M001")


async def test_no_model_accepts_the_cheapest(world):
    msg, used = await ask(NoLLM(), world)
    assert msg.type == MessageType.ACCEPT
    assert msg.chosen_option == 0
    assert msg.body == "Water accepts option A for W-001: shared trench, 10–14 Nov. Saves ₹3,36,000."
    assert msg.sender == "water"
    assert msg.recipients == ["coordinator"]
    assert used is False


async def test_model_counter_with_a_reason(world):
    llm = FakeLLM(Pick(option=1, reason="Our crew is busy that week"))
    msg, used = await ask(llm, world)
    assert msg.type == MessageType.COUNTER
    assert msg.chosen_option == 1
    assert msg.body == ("Water asks for option B for W-001: move after T-001, 15–19 Nov. Costs ₹10,000 more. "
                        "Our crew is busy that week.")
    assert used is True
    system, user = llm.calls[0]
    assert "Water department" in system
    assert all(o.label in user for o in world[3])
    assert "saves ₹3,36,000" in user
    assert "The coordinator proposes option 0." in user


async def test_user_text_describes_the_work(world):
    llm = FakeLLM(None)
    await ask(llm, world)
    user = llm.calls[0][1]
    assert user.startswith("Clash: T-001 and W-001 dig Test Road on the same days.\n")
    assert "Your work: W-001 · Water main, Test Road · 400 m · asked for 10–14 Nov · allowed 2 Nov to 29 Nov · priority 3 of 5" in user
    assert "Now planned: 10–14 Nov · open cut" in user


async def test_bad_model_answer_falls_back(world):
    msg, used = await ask(FakeLLM(Pick(option=7, reason="Anything")), world)
    assert (msg.type, msg.chosen_option, used) == (MessageType.ACCEPT, 0, False)
    assert msg.body.endswith("Saves ₹3,36,000.")


async def test_missing_model_answer_falls_back(world):
    msg, used = await ask(FakeLLM(None), world)
    assert (msg.type, msg.chosen_option, used) == (MessageType.ACCEPT, 0, False)


async def test_a_reason_with_a_digit_is_dropped(world):
    msg, used = await ask(FakeLLM(Pick(option=0, reason="Ready by 9 Nov")), world)
    assert msg.body == "Water accepts option A for W-001: shared trench, 10–14 Nov. Saves ₹3,36,000."
    assert used is True


async def test_minus_one_escalates(world):
    msg, used = await ask(FakeLLM(Pick(option=-1, reason="No crew")), world)
    assert msg.type == MessageType.ESCALATE
    assert msg.chosen_option is None
    assert msg.body == "Water cannot take any of these options for W-001. The scheduler decides. No crew."
    assert used is True


async def test_no_options_escalates_without_asking(world):
    llm = FakeLLM(Pick(option=0, reason="x"))
    msg, used = await ask(llm, world, options=[])
    assert msg.type == MessageType.ESCALATE
    assert msg.chosen_option is None
    assert llm.calls == []
    assert used is False


async def test_a_long_reason_is_cut_to_one_sentence(world):
    msg, _ = await ask(FakeLLM(Pick(option=0, reason="word " * 60)), world)
    reason = msg.body.split("Saves ₹3,36,000. ")[1]
    assert len(reason) == 160
    assert reason.endswith(".")
    assert not any(ch.isdigit() for ch in reason)
