import time

from backend.app import store
from backend.app.deps import in_session
from backend.app.main import app


def wait_for_run(client, run_id: str) -> dict:
    """Poll until the background run leaves 'running' (up to 5 s)."""
    for _ in range(100):
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.05)
    raise AssertionError(f"{run_id} still running")


def test_old_way_and_solver_only(client):
    old = client.post("/plan/naive").json()
    assert (old["plan_id"], old["variant"], old["status"]) == ("P-OLD-1", "naive", "draft")
    solo = client.post("/plan/solver-only").json()
    assert (solo["plan_id"], solo["variant"], solo["status"]) == ("P-SOLO-1", "solver_only", "draft")
    assert {p["plan_id"] for p in client.get("/plans").json()} == {"P-OLD-1", "P-SOLO-1"}


def test_orchestrate_waits_for_approval(client):
    started = client.post("/plan/orchestrate").json()
    assert (started["run_id"], started["status"]) == ("RUN-0001", "running")
    run = wait_for_run(client, "RUN-0001")
    assert (run["status"], run["plan_id"], run["approval_id"]) == ("waiting_approval", "P-FAKE", "A-0001")
    assert [a.run_id for a in in_session(store.list_approvals, "pending")] == ["RUN-0001"]
    messages = client.get("/negotiation").json()
    assert [(m["msg_id"], m["sender"]) for m in messages] == [("M1", "coordinator")]
    assert client.get("/negotiation", params={"run_id": "RUN-0001"}).json() == messages
    assert client.get("/plan/P-FAKE").json()["status"] == "waiting_approval"


def test_metrics_and_diff(client):
    assert client.get("/plan/P-OLD-1/metrics").json()["plan_id"] == "P-OLD-1"
    assert client.get("/plan/P-OLD-1/diff", params={"against": "naive"}).json() == []
    assert client.get("/plan/P-OLD-1/diff", params={"against": "P-NOPE"}).status_code == 404
    assert client.get("/plan/NOPE").status_code == 404
    assert client.get("/runs/RUN-9999").status_code == 404
    assert client.get("/negotiation").json() == []


def test_failed_run_is_recorded(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("workflow broke")

    monkeypatch.setattr(app.state.wiring, "start_run", boom)
    run_id = client.post("/plan/orchestrate").json()["run_id"]
    run = wait_for_run(client, run_id)
    assert (run["status"], run["note"]) == ("failed", "The plan could not be made.")
