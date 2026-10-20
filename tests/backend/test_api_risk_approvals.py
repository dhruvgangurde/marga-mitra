from tests.backend.test_api_plans import wait_for_run

PROCESSION = {"label": "Procession, 20 Nov", "start_day": 18, "end_day": 18, "segment_ids": ["S-0001"]}


def test_forecast_override_starts_a_replan(client):
    r = client.post("/risk/forecast-override", json={"kind": "rain", "start_day": 12, "end_day": 13, "value": 70})
    assert (r.json()["run_id"], r.json()["status"]) == ("RUN-0001", "running")
    windows = {w["window_id"]: w for w in client.get("/risk/windows").json()}
    assert (windows["OV-1"]["source"], windows["OV-1"]["label"]) == ("override", "Heavy rain, 14–15 Nov")
    entries = client.get("/ledger").json()
    override = next(e for e in entries if e["action"] == "forecast.override")
    assert override["summary"] == "Heavy rain 14–15 Nov (simulated for the demo)"
    assert wait_for_run(client, "RUN-0001")["status"] == "waiting_approval"
    assert client.post("/risk/forecast-override", json={"kind": "event", "start_day": 12, "end_day": 13, "value": 70}).status_code == 422
    assert client.post("/risk/forecast-override", json={"kind": "rain", "start_day": 12, "end_day": 11, "value": 70}).status_code == 422


def test_event_is_stored(client):
    w = client.post("/events", json=PROCESSION).json()
    assert (w["window_id"], w["kind"], w["source"], w["value"]) == ("EV-1", "event", "event", 0.0)
    assert "EV-1" in {x["window_id"] for x in client.get("/risk/windows").json()}
    assert client.post("/events", json={**PROCESSION, "segment_ids": ["S-9999"]}).status_code == 422
    assert client.post("/events", json={**PROCESSION, "segment_ids": []}).status_code == 422
    assert client.post("/events", json={**PROCESSION, "start_day": 30, "end_day": 30}).status_code == 422


def test_approve_once(client):
    client.post("/plan/orchestrate")
    run = wait_for_run(client, "RUN-0001")
    aid = run["approval_id"]
    assert [a["approval_id"] for a in client.get("/approvals", params={"status": "pending"}).json()] == [aid]
    assert client.post(f"/approvals/{aid}", json={"decision": "reject", "by": "ward_engineer"}).status_code == 422
    r = client.post(f"/approvals/{aid}", json={"decision": "approve", "by": "ward_engineer"})
    assert r.json()["status"] == "approved"
    assert client.get("/plan/P-FAKE").json()["status"] == "approved"
    assert client.get("/runs/RUN-0001").json()["status"] == "approved"
    assert client.get("/approvals", params={"status": "pending"}).json() == []
    assert client.get("/ledger", params={"limit": 1}).json()[0]["action"] == "plan.approved"
    assert client.post(f"/approvals/{aid}", json={"decision": "approve", "by": "ward_engineer"}).status_code == 409
    assert client.post("/approvals/A-9999", json={"decision": "approve", "by": "ward_engineer"}).status_code == 404


def test_approval_counts_when_the_run_has_stopped(client, monkeypatch):
    client.post("/plan/orchestrate")
    aid = wait_for_run(client, "RUN-0001")["approval_id"]

    async def stopped(*args, **kwargs):
        raise RuntimeError("Run RUN-0001 is not waiting for approval.")

    monkeypatch.setattr(client.app.state.wiring, "resume_run", stopped)
    r = client.post(f"/approvals/{aid}", json={"decision": "approve", "by": "ward_engineer"})
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["note"]) == ("approved", "Saved without the planning run, which had stopped.")
    assert client.get("/plan/P-FAKE").json()["status"] == "approved"
    assert client.get("/runs/RUN-0001").json()["status"] == "approved"
    newest = client.get("/ledger", params={"limit": 1}).json()[0]
    assert (newest["action"], newest["actor"], newest["summary"]) == (
        "plan.approved", "ward_engineer", "Approved the plan for 2–29 Nov")
    assert client.post(f"/approvals/{aid}", json={"decision": "approve", "by": "ward_engineer"}).status_code == 409


def test_record_pages_and_check(client):
    client.post("/events", json=PROCESSION)
    assert [e["seq"] for e in client.get("/ledger", params={"limit": 1}).json()] == [2]
    assert [e["seq"] for e in client.get("/ledger", params={"before_seq": 2}).json()] == [1]
    assert client.get("/ledger", params={"limit": 0}).status_code == 422
    assert client.get("/ledger/verify").json() == {"ok": True, "entries": 2, "first_bad_seq": None}


def test_socket_gets_live_events(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/events", json=PROCESSION)
        types = {ws.receive_json()["type"], ws.receive_json()["type"]}
    assert types == {"ledger.appended", "risk.windows_changed"}
