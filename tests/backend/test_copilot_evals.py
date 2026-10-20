import pytest

from backend.app.config import get_settings
from contracts.fakes import now
from contracts.models import CopilotReply, EvalRow, EvalSummary, Stat

ASK = {"message": "Show every dig on Munchur Road next week", "context": {"day": 8, "tab": "works"}}


def test_copilot_answers_on_the_stand_in(client):
    with client.websocket_connect("/ws") as ws:
        r = client.post("/copilot", json=ASK)
        assert ws.receive_json()["type"] == "copilot.step"
    reply = r.json()
    assert (r.status_code, reply["text"], reply["used_llm"]) == (200, "The copilot is not connected yet.", False)
    assert [s["status"] for s in reply["steps"]] == ["done"]


def test_copilot_gets_the_context_and_its_failures_are_plain(client, monkeypatch):
    wiring = client.app.state.wiring
    calls = []

    async def recorder(*args):
        calls.append(args)
        return CopilotReply(reply_id="CP-1", text="ok", used_llm=False)

    monkeypatch.setattr(wiring, "run_copilot", recorder)
    assert client.post("/copilot", json={**ASK, "context": {**ASK["context"], "zoom": 3}}).status_code == 200
    assert calls == [(ASK["message"], {"day": 8, "tab": "works", "selected_work": None, "plan_id": None},
                      "http://127.0.0.1:8000", wiring.deps.emit)]

    async def broken(*args):
        raise RuntimeError("no")

    monkeypatch.setattr(wiring, "run_copilot", broken)
    r = client.post("/copilot", json=ASK)
    assert (r.status_code, r.json()["detail"]) == (503, "The copilot could not answer. Try again.")
    for bad in ({"message": ""}, {"message": "x" * 501}, {**ASK, "context": {"day": 30}}):
        assert client.post("/copilot", json=bad).status_code == 422


@pytest.fixture
def summary_file(tmp_path, monkeypatch):
    path = tmp_path / "summary.json"
    monkeypatch.setenv("EVALS_SUMMARY_PATH", str(path))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def test_evals_summary(client, summary_file):
    r = client.get("/evals/summary")
    assert (r.status_code, r.json()["detail"]) == (404, "No results yet.")
    stat = Stat(median=1.0, low=0.5, high=2.0)
    summary = EvalSummary(seeds=[1, 2], rows=[EvalRow(variant="naive", digs_per_road=stat, lane_closure_hours=stat,
                                                      trench_hours_in_rain=stat, clashes=stat, days_late=stat,
                                                      cost_inr=stat)],
                          fake_repairs_caught=9, fake_repairs_total=10, generated_at=now())
    summary_file.write_text(summary.model_dump_json(), encoding="utf-8")
    r = client.get("/evals/summary")
    assert r.status_code == 200 and EvalSummary.model_validate(r.json()) == summary
    summary_file.write_text("{", encoding="utf-8")
    r = client.get("/evals/summary")
    assert (r.status_code, r.json()["detail"]) == (500, "The results file could not be read.")
