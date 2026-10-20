from backend.app.routers.works import work_status
from contracts.fakes import now, tiny_scenario
from contracts.models import Assignment, Mode, Verification, WorkStatus


def _at(start: int, mode: Mode = Mode.open_cut, group: str | None = None) -> Assignment:
    return Assignment(work_id="T-001", start_day=start, end_day=start + 2, mode=mode, shared_group=group)


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "db": True, "llm_provider": "none", "weather_mode": "fixture"}


def test_startup_loads_test_case(client):
    plans = client.get("/plans").json()
    assert [(p["plan_id"], p["variant"], p["status"]) for p in plans] == [("P-OLD-1", "naive", "draft")]
    entries = client.get("/ledger").json()
    assert [(e["seq"], e["action"]) for e in entries] == [(1, "scenario.loaded")]
    assert entries[0]["summary"] == "Loaded test case 1: 4 works on 3 road segments"


def test_segments_and_bbox(client):
    features = client.get("/segments").json()["features"]
    assert len(features) == 3
    assert all(f["geometry"]["type"] == "LineString" for f in features)
    assert all(set(f["properties"]) == {"segment_id", "name", "road_class", "low_lying", "protected_until"} for f in features)
    picked = client.get("/segments", params={"bbox": "74.789,13.0,74.7915,13.02"}).json()["features"]
    assert [f["properties"]["segment_id"] for f in picked] == ["S-0001"]
    assert client.get("/segments", params={"bbox": "1,2,3"}).status_code == 422
    assert client.get("/segments", params={"bbox": "a,b,c,d"}).status_code == 422


def test_departments(client):
    depts = client.get("/departments").json()
    assert len(depts) == 6
    assert depts[0] == {"id": "water", "name": "Water", "icon": "drop", "color_token": "--dept-water"}
    assert [d["id"] for d in depts] == ["water", "drainage", "gas", "power", "telecom", "roads"]


def test_works_with_status(client):
    views = client.get("/works").json()
    assert {v["work"]["work_id"]: v["status"] for v in views} == {
        "W-001": "digging", "T-001": "planned", "G-001": "planned", "R-001": "planned"}
    assert client.get("/works/T-001").json()["assignment"]["start_day"] == 10
    assert client.get("/works/X-999").status_code == 404
    assert client.get("/works", params={"plan_id": "P-NOPE"}).status_code == 404


def test_work_status_order():
    w = tiny_scenario(1).works[1]  # T-001, asked for days 10-12, open cut
    digging_shared_moved = _at(8, Mode.trenchless, "G1")
    everything = w.model_copy(update={"is_emergency": True, "done": True})
    assert work_status(everything, digging_shared_moved, 8) == WorkStatus.emergency
    assert work_status(w.model_copy(update={"done": True}), digging_shared_moved, 8) == WorkStatus.done
    assert work_status(w, digging_shared_moved, 8) == WorkStatus.digging
    assert work_status(w, digging_shared_moved, 20) == WorkStatus.shared
    assert work_status(w, _at(10, Mode.trenchless), 20) == WorkStatus.moved
    assert work_status(w, _at(11), 20) == WorkStatus.moved
    assert work_status(w, _at(10), 20) == WorkStatus.planned
    assert work_status(w, None, 8) == WorkStatus.planned


def test_work_status_with_a_check():
    w = tiny_scenario(1).works[1]
    digging = _at(8)

    def check(result: str) -> Verification:
        return Verification(verification_id="V-0001", work_id="T-001", result=result, checks=[], deposit_inr=100000,
                            deposit_released=result == "verified", decided_at=now())

    emergency = w.model_copy(update={"is_emergency": True})
    assert work_status(emergency, digging, 8, check("verified")) == WorkStatus.emergency
    assert work_status(w.model_copy(update={"done": True}), digging, 8, check("verified")) == WorkStatus.verified
    assert work_status(w.model_copy(update={"done": True}), digging, 8, check("held")) == WorkStatus.held
    assert work_status(w, digging, 8, check("held")) == WorkStatus.held
    assert work_status(w, digging, 8, check("inspect")) == WorkStatus.digging
    assert work_status(w, digging, 8, check("pending")) == WorkStatus.digging


def test_add_work(client):
    gas = tiny_scenario(1).works[2].model_copy(update={"work_id": "G-002"}).model_dump(mode="json")
    r = client.post("/works", json=gas)
    assert r.status_code == 201 and r.json()["work_id"] == "G-002"
    assert client.get("/works/G-002").status_code == 200
    assert client.post("/works", json=gas).status_code == 409
    assert client.post("/works", json={**gas, "work_id": "G-003", "segment_ids": ["S-9999"]}).status_code == 422
    newest = client.get("/ledger", params={"limit": 1}).json()[0]
    assert (newest["action"], newest["actor"], newest["entity"]) == ("work.added", "gas", "work:G-002")
    assert newest["summary"] == "Gas added G-002: Gas line, Test Road"


def test_scenario_load_switches_seed(client):
    r = client.post("/scenario/load", params={"seed": 2})
    assert r.json() == {"seed": 2, "start_date": "2026-11-02", "works": 4, "segments": 3}
    assert [p["plan_id"] for p in client.get("/plans").json()] == ["P-OLD-2"]
    assert client.post("/scenario/load", params={"seed": 0}).status_code == 422


def test_scenario_load_is_broadcast(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/scenario/load", params={"seed": 2})
        for _ in range(5):
            msg = ws.receive_json()
            if msg["type"] == "ledger.appended" and msg["data"]["action"] == "scenario.loaded":
                break
        else:
            raise AssertionError("no scenario.loaded entry on /ws")
    assert msg["data"]["summary"] == "Loaded test case 2: 4 works on 3 road segments"
