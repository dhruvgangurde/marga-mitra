from datetime import datetime

from backend.app.verify import vision
from backend.app.verify.exif import INDIA
from contracts.fakes import tiny_scenario
from scripts.make_demo_photos import make_photo, site_point, with_facts
from tests.backend.test_api_evidence import upload
from tests.backend.test_api_plans import wait_for_run
from tests.backend.test_api_verify import CleanRepair

S = tiny_scenario(1)
REUSED = ("The before photo of T-001 is the same as the before photo of W-001 (100% alike). "
          "Money is held and an inspector visits on 12 Nov.")


def _photo(scene: str, seed: int, day: int) -> bytes:
    lat, lon = site_point(S, "W-001", 12)
    return with_facts(make_photo(scene, seed), lat, lon, datetime(2026, 11, day, 9, 0, tzinfo=INDIA))


def _flag_entries(client) -> list[dict]:
    return [e for e in client.get("/ledger", params={"limit": 500}).json() if e["action"] == "auditor.flag"]


def test_reused_photo_raises_one_flag(client, uploads_dir, monkeypatch):
    monkeypatch.setattr(vision, "llm_and_model", lambda: (CleanRepair(), "vision-test-model"))
    before = _photo("open", 1041, 10)
    for work_id, kind, data in (("W-001", "before", before), ("T-001", "before", before),
                                ("T-001", "after", _photo("patched", 2301, 14))):
        assert upload(client, work_id, kind, data).status_code == 201

    with client.websocket_connect("/ws") as ws:
        assert client.post("/works/T-001/verify").json()["result"] == "held"
        types: list[str] = []
        while len(types) < 8 and "auditor.flag" not in types:
            types.append(ws.receive_json()["type"])
    assert "auditor.flag" in types

    [flag] = client.get("/auditor/flags").json()
    [entry] = _flag_entries(client)
    assert (flag["flag_id"], flag["severity"], flag["word"], flag["work_id"], flag["text"]) == (
        "F-0001", "fail", "Photo reused", "T-001", REUSED)
    assert flag["ledger_seq"] == entry["seq"]
    assert (entry["actor"], entry["summary"]) == ("auditor", "Photo reused at T-001: money stays held")

    client.post("/works/T-001/verify")
    client.post("/plan/orchestrate")
    aid = wait_for_run(client, "RUN-0001")["approval_id"]
    assert client.post(f"/approvals/{aid}", json={"decision": "approve", "by": "ward_engineer"}).status_code == 200
    assert client.get("/auditor/flags").json() == [flag]
    assert len(_flag_entries(client)) == 1
