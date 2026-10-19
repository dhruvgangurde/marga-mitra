import asyncio
import time

import pytest

from agents import coordinator
from agents.conflicts import cluster_conflicts, detect_conflicts
from agents.coordinator import between_label, current, is_keep, listing, negotiate, work_clash, work_options
from agents.department import DepartmentAgent, Pick
from agents.tools import options_for
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import ConflictKind, RiskWindow, SolveConstraints


@pytest.fixture
def s():
    return tiny_scenario()


@pytest.fixture
def p(s):
    return fake_naive_plan(s)


@pytest.fixture
def cluster(s, p):
    return cluster_conflicts(detect_conflicts(s, p))[0]


def labels(opts):
    return [o.label for o in opts]


def costs_of(opts):
    return [o.cost_delta_inr for o in opts]


def test_options_for_water_across_the_cluster(s, p, cluster):
    opts = work_options(cluster, s, p, "W-001")
    assert labels(opts) == ["A · Finish before resurfacing, 6–10 Nov", "B · Shared trench, 10–14 Nov",
                            "C · Move after T-001, 15–19 Nov", "D · Keep 10–14 Nov",
                            "E · Move after the heavy rain, 16–20 Nov", "F · Move before the heavy rain, 9–13 Nov"]
    assert costs_of(opts) == [0, -336000, 10000, 0, 12000, 0]


def test_options_for_telecom_across_the_cluster(s, p, cluster):
    opts = work_options(cluster, s, p, "T-001")
    assert labels(opts) == ["A · Finish before resurfacing, 8–10 Nov", "B · Trenchless, 12–15 Nov",
                            "C · Shared trench, 10–14 Nov", "D · Move after W-001, 15–17 Nov", "E · Keep 12–14 Nov",
                            "F · Move after the heavy rain, 16–18 Nov", "G · Move before the heavy rain, 11–13 Nov"]
    assert costs_of(opts) == [0, 64800, -336000, 6000, 0, 8000, 0]


def test_options_for_roads_and_gas(s, p, cluster):
    roads = work_options(cluster, s, p, "R-001")
    assert labels(roads) == ["A · Resurface after every dig, 15–17 Nov"]
    assert costs_of(roads) == [8000]
    gas = work_options(cluster, s, p, "G-001")
    assert labels(gas) == ["A · Finish before resurfacing, 7–10 Nov", "B · Trenchless, 11–15 Nov"]
    assert costs_of(gas) == [0, 273600]


def test_a_work_outside_the_cluster_has_no_options(s, p, cluster):
    assert work_options(cluster, s, p, "X-999") == []


def test_work_clash_joins_every_note_of_the_work(cluster):
    clash = work_clash(cluster, "G-001")
    assert clash.conflict_id == "C1"
    assert clash.note == "G-001 digs Test Road during or after resurfacing R-001."
    water = work_clash(cluster, "W-001")
    assert water.conflict_id == "C3"
    assert water.note.count(".") == 3
    assert "W-001 is open during Heavy rain, 14–15 Nov." in water.note


def test_current_falls_back_to_the_departments_ask(s, p):
    water = next(w for w in s.works if w.work_id == "W-001")
    assert current(p, water) == (8, water.modes[0].mode)
    empty = p.model_copy(update={"assignments": []})
    assert current(empty, water) == (8, water.modes[0].mode)


def test_only_the_keep_options_keep(s, p, cluster):
    works = {w.work_id: w for w in s.works}
    for work_id in ("W-001", "T-001", "R-001", "G-001"):
        keeps = [o.label for o in work_options(cluster, s, p, work_id) if is_keep(o, p, works[work_id])]
        expected = {"W-001": ["D · Keep 10–14 Nov"], "T-001": ["E · Keep 12–14 Nov"]}.get(work_id, [])
        assert keeps == expected


def _in_one_trench(p, t_start=8, t_end=12):
    moved = []
    for a in p.assignments:
        if a.work_id == "W-001":
            a = a.model_copy(update={"start_day": 8, "end_day": 12, "shared_group": "G1"})
        elif a.work_id == "T-001":
            a = a.model_copy(update={"start_day": t_start, "end_day": t_end, "shared_group": "G1"})
        moved.append(a)
    return p.model_copy(update={"assignments": moved})


def test_a_work_already_in_a_trench_keeps_it(s, p, cluster):
    shared = _in_one_trench(p)
    c4 = next(c for c in cluster if c.conflict_id == "C4")
    water = next(w for w in s.works if w.work_id == "W-001")
    opts = options_for(c4, s, shared, "W-001")
    # Phase 1 drops a Keep that repeats the trench option, so the trench option is the one that keeps
    kept = [o for o in opts if o.shared_group == "G1" and o.start_day == 8]
    assert len(kept) == 1
    assert is_keep(kept[0], shared, water)
    assert not is_keep(next(o for o in opts if o.label.startswith("B")), shared, water)


def test_keep_copies_the_trench_when_it_differs_from_the_trench_option(s, p, cluster):
    shared = _in_one_trench(p, t_start=6, t_end=8)
    c4 = next(c for c in cluster if c.conflict_id == "C4")
    water = next(w for w in s.works if w.work_id == "W-001")
    opts = options_for(c4, s, shared, "W-001")
    keep = next(o for o in opts if " Keep " in o.label)
    assert keep.shared_group == "G1"
    assert keep.start_day == 8
    assert is_keep(keep, shared, water)
    trench = next(o for o in opts if " Shared trench" in o.label)
    assert not is_keep(trench, shared, water)


def test_listing():
    assert listing(["W-001"]) == "W-001"
    assert listing(["W-001", "T-001"]) == "W-001 and T-001"
    assert listing(["W-001", "T-001", "G-001"]) == "W-001, T-001 and G-001"


def test_between_label(s):
    assert between_label(s, 9, 12) == "11 and 14 Nov"
    assert between_label(s, 28, 30) == "30 Nov and 2 Dec"


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)


async def test_round_one_without_a_model(s, p):
    emit = Recorder()
    out = await negotiate(s, p, detect_conflicts(s, p), "RUN-1", emit)
    msgs = out.messages
    assert [m.msg_id for m in msgs] == ["M001", "M002", "M003", "M004", "M005"]
    assert all(m.round == 1 and m.run_id == "RUN-1" for m in msgs)
    notice = msgs[0]
    assert (notice.type.value, notice.sender) == ("NOTICE", "coordinator")
    assert notice.recipients == ["Water", "Telecom", "Gas", "Roads"]
    assert notice.work_ids == ["W-001", "T-001", "G-001", "R-001"]
    assert notice.body == "4 works clash on Test Road between 11 and 14 Nov: W-001, T-001, G-001 and R-001."
    assert [(m.type.value, m.sender, m.recipients) for m in msgs[1:]] == [("ACCEPT", d, ["Coordinator"]) for d in
                                                                         ("water", "telecom", "gas", "roads")]
    assert [m.body for m in msgs[1:]] == [
        "Water accepts option B for W-001: shared trench, 10–14 Nov. Saves ₹3,36,000.",
        "Telecom accepts option C for T-001: shared trench, 10–14 Nov. Saves ₹3,36,000.",
        "Gas accepts option A for G-001: finish before resurfacing, 7–10 Nov. No extra cost.",
        "Roads accepts option A for R-001: resurface after every dig, 15–17 Nov. Costs ₹8,000 more.",
    ]
    assert [e.type for e in emit.events] == ["negotiation.message"] * 5
    assert [e.data for e in emit.events] == [m.model_dump(mode="json") for m in msgs]
    assert (out.rounds, out.escalated, out.used_llm) == (1, [], False)
    c = out.constraints
    assert c.shared_groups == ["G1"]
    assert c.min_start == {"R-001": 13}
    assert c.pinned_start == {"G-001": 5}
    assert c.forbidden_days == {}


async def test_no_clashes_no_talk(s, p):
    emit = Recorder()
    out = await negotiate(s, p, [], "RUN-1", emit)
    assert out.messages == []
    assert emit.events == []
    assert out.rounds == 0
    assert out.constraints == SolveConstraints()
    assert out.used_llm is False


class ScriptLLM:
    provider = "fake"

    def __init__(self, script):
        self.script = script
        self.calls = {}

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        name = next(n for n in ("Water", "Drainage", "Gas", "Power", "Telecom", "Roads") if f"{n} department" in system)
        k = self.calls.get(name, 0)
        self.calls[name] = k + 1
        answers = self.script.get(name, [])
        if k >= len(answers):
            return None
        return Pick(option=answers[k], reason="Our crew prefers these dates")


class SlowLLM:
    provider = "fake"

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        await asyncio.sleep(1)
        return Pick(option=0, reason="ok")


class EscalateLLM:
    provider = "fake"

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        return Pick(option=-1, reason="We cannot do this")


def use(monkeypatch, llm):
    monkeypatch.setattr(coordinator, "make_agent", lambda dept: DepartmentAgent(dept, llm=llm))


async def test_a_trench_mismatch_goes_to_round_two(s, p, monkeypatch):
    use(monkeypatch, ScriptLLM({"Telecom": [4, 2]}))
    out = await negotiate(s, p, detect_conflicts(s, p), "RUN-1", Recorder())
    msgs = out.messages
    assert [m.type.value for m in msgs] == ["NOTICE", "ACCEPT", "COUNTER", "ACCEPT", "ACCEPT", "NOTICE", "ACCEPT", "ACCEPT"]
    assert [m.round for m in msgs] == [1, 1, 1, 1, 1, 2, 2, 2]
    assert msgs[2].msg_id == "M003"
    assert msgs[2].sender == "telecom"
    assert msgs[2].chosen_option == 4
    assert msgs[5].body == ("Round 2: W-001 and T-001 still disagree. "
                            "The coordinator proposes option B for W-001 and option C for T-001.")
    assert msgs[5].recipients == ["Water", "Telecom"]
    assert (out.rounds, out.constraints.shared_groups, out.used_llm) == (2, ["G1"], True)


async def test_no_agreement_after_three_rounds_goes_to_the_scheduler(s, p, monkeypatch):
    use(monkeypatch, ScriptLLM({"Telecom": [4, 4, 4]}))
    out = await negotiate(s, p, detect_conflicts(s, p), "RUN-1", Recorder())
    assert out.rounds == 3
    assert len(out.messages) == 12
    last = out.messages[-1]
    assert (last.msg_id, last.type.value, last.sender, last.recipients) == ("M012", "ESCALATE", "coordinator", ["Scheduler"])
    assert last.body == "The scheduler decides the remaining dates for W-001 and T-001."
    assert out.escalated == ["T-001", "W-001"]
    c = out.constraints
    assert c.shared_groups == []
    assert "W-001" not in c.min_start | c.pinned_start
    assert "T-001" not in c.min_start | c.pinned_start
    assert c.min_start == {"R-001": 13}
    assert c.pinned_start == {"G-001": 5}


async def test_slow_agents_fall_back_to_the_cost_tables(s, p, monkeypatch):
    use(monkeypatch, SlowLLM())
    monkeypatch.setattr(coordinator, "_round_timeout", lambda: 0.05)
    begin = time.perf_counter()
    out = await negotiate(s, p, detect_conflicts(s, p), "RUN-1", Recorder())
    assert time.perf_counter() - begin < 1
    assert [m.body for m in out.messages[1:]] == [
        "Water accepts option B for W-001: shared trench, 10–14 Nov. Saves ₹3,36,000.",
        "Telecom accepts option C for T-001: shared trench, 10–14 Nov. Saves ₹3,36,000.",
        "Gas accepts option A for G-001: finish before resurfacing, 7–10 Nov. No extra cost.",
        "Roads accepts option A for R-001: resurface after every dig, 15–17 Nov. Costs ₹8,000 more.",
    ]
    assert len(out.messages) == 5
    assert out.used_llm is False


async def test_departments_that_refuse_leave_it_to_the_scheduler(s, p, monkeypatch):
    use(monkeypatch, EscalateLLM())
    out = await negotiate(s, p, detect_conflicts(s, p), "RUN-1", Recorder())
    msgs = out.messages
    assert len(msgs) == 6
    assert [m.type.value for m in msgs[1:5]] == ["ESCALATE"] * 4
    assert msgs[1].body.startswith("Water cannot take any of these options for W-001.")
    assert msgs[5].body == "The scheduler decides the remaining dates for W-001, T-001, G-001 and R-001."
    assert out.escalated == ["G-001", "R-001", "T-001", "W-001"]
    assert out.constraints == SolveConstraints()
    assert (out.rounds, out.used_llm) == (1, True)


async def test_two_keepers_on_a_clash_make_the_lower_priority_one_move(s, p, monkeypatch):
    works = [w.model_copy(update={"priority": 5}) if w.work_id == "T-001" else w for w in s.works]
    s5 = s.model_copy(update={"works": works, "parallel_groups": []})
    only_same_road = [c for c in detect_conflicts(s5, p) if c.kind.value == "same_road"]
    # round 1: both keep (Water's B, Telecom's C); round 2: Water takes the move it is proposed
    use(monkeypatch, ScriptLLM({"Water": [1, 0], "Telecom": [2, 2]}))
    out = await negotiate(s5, p, only_same_road, "RUN-1", Recorder())
    notice = next(m for m in out.messages if m.round == 2 and m.type.value == "NOTICE")
    assert notice.body == ("Round 2: W-001 and T-001 still disagree. "
                           "The coordinator proposes option A for W-001 and option C for T-001.")
    assert out.rounds == 2
    assert out.escalated == []
    assert out.constraints.min_start == {"W-001": 13}
    assert out.constraints.pinned_start == {"T-001": 10}


def _risk_only(scenario, plan):
    return [c for c in detect_conflicts(scenario, plan) if c.kind == ConflictKind.risk]


async def test_one_forecast_is_one_notice(s, p):
    rain = RiskWindow(window_id="R1", kind="rain", start_day=12, end_day=13, segment_ids=["S-0002", "S-0003"], value=70,
                      source="fixture", label="Heavy rain, 14–15 Nov")
    s2 = s.model_copy(update={"risk_windows": [rain]})
    p2 = p.model_copy(update={"assignments": [a.model_copy(update={"start_day": 11, "end_day": 14})
                                              if a.work_id == "G-001" else a for a in p.assignments]})
    risk = _risk_only(s2, p2)
    assert len(cluster_conflicts(risk)) == 2
    out = await negotiate(s2, p2, risk, "RUN-1", Recorder())
    notices = [m for m in out.messages if m.type.value == "NOTICE"]
    assert len(notices) == 1
    assert notices[0].recipients == ["Water", "Telecom", "Gas"]
    assert notices[0].body == "Heavy rain is forecast for 14–15 Nov. W-001, T-001 and G-001 are open on low-lying roads then."
    assert [m.type.value for m in out.messages[1:]] == ["ACCEPT"] * 3
    assert out.constraints.pinned_start == {"W-001": 7, "T-001": 9, "G-001": 8}


async def test_an_event_notice_names_its_route(s, p):
    event = RiskWindow(window_id="EV-1", kind="event", start_day=10, end_day=10, segment_ids=["S-0003"], value=0,
                       source="event", label="Procession, 12 Nov")
    s3 = s.model_copy(update={"risk_windows": [event]})
    out = await negotiate(s3, p, _risk_only(s3, p), "RUN-1", Recorder())
    assert out.messages[0].body == "Procession on 12 Nov. G-001 and R-001 are on its route."


def test_a_single_work_reads_is_not_are(s, p):
    rain = RiskWindow(window_id="R1", kind="rain", start_day=12, end_day=13, segment_ids=["S-0003"], value=70,
                      source="fixture", label="Heavy rain, 14–15 Nov")
    s4 = s.model_copy(update={"risk_windows": [rain]})
    p4 = p.model_copy(update={"assignments": [a.model_copy(update={"start_day": 11, "end_day": 14})
                                              if a.work_id == "G-001" else a for a in p.assignments]})
    only = [c for c in _risk_only(s4, p4)]
    assert len(only) == 1
    works = [w for w in s4.works if w.work_id == "G-001"]
    assert coordinator._notice_body(only, works, s4) == "Heavy rain is forecast for 14–15 Nov. G-001 is open on low-lying roads then."
