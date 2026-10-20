from datetime import date

import pytest

from backend.app import deps, store
from backend.app.db import session
from backend.app.ws import hub
from contracts import interfaces
from contracts.fakes import now, tiny_scenario
from contracts.models import NegotiationMessage, WsEvent


@pytest.fixture
def wiring(db, monkeypatch):
    monkeypatch.setattr(deps, "real_impl", lambda name: None)
    return deps.build_wiring()


def test_real_impl_is_none_for_a_missing_module(monkeypatch):
    monkeypatch.setattr(interfaces, "IMPLEMENTATIONS", {"x": "no_such_module_mm:f", "y": "contracts.costs:inr"})
    assert deps.real_impl("x") is None
    assert deps.real_impl("y")(240000) == "₹2,40,000"


def test_day_range():
    start = date(2026, 11, 2)
    assert deps.day_range(start, 12, 13) == "14–15 Nov"
    assert deps.day_range(start, 0, 27) == "2–29 Nov"
    assert deps.day_range(start, 28, 30) == "30 Nov – 2 Dec"


def test_generate_scenario_is_stored(wiring):
    assert "generate_scenario" in wiring.fakes
    assert wiring.deps.generate_scenario(1) == tiny_scenario(1)
    with session() as s:
        assert store.get_scenario(s, 1) == tiny_scenario(1)
        store.add_work(s, 1, tiny_scenario(1).works[2].model_copy(update={"work_id": "G-002"}))
    assert wiring.deps.generate_scenario(1).works[-1].work_id == "G-002"


async def test_emit_saves_negotiation_messages(wiring):
    msg = NegotiationMessage(msg_id="M1", run_id="RUN-0001", round=1, sender="coordinator", recipients=["water"],
                             type="NOTICE", work_ids=["W-001"], body="2 works clash on Test Road.", ts=now())
    await wiring.deps.emit(WsEvent(type="negotiation.message", data=msg.model_dump(mode="json"), ts=now()))
    with session() as s:
        assert store.list_messages(s, "RUN-0001") == [msg]


async def test_ledger_append_broadcasts(wiring):
    class Socket:
        def __init__(self) -> None:
            self.sent: list[dict] = []

        async def send_json(self, data: dict) -> None:
            self.sent.append(data)

    sock = Socket()
    hub.sockets.add(sock)
    try:
        entry = await wiring.deps.ledger_append("system", "test.added", "test:1", "Test entry", {"n": 1})
    finally:
        hub.sockets.discard(sock)
    assert [m["type"] for m in sock.sent] == ["ledger.appended"]
    assert sock.sent[0]["data"]["seq"] == entry.seq == 1
