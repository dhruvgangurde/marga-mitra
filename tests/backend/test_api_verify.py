from datetime import datetime

import pytest

from backend.app.verify import vision
from backend.app.verify.exif import INDIA
from backend.app.verify.vision import RepairView
from contracts.fakes import tiny_scenario
from scripts.make_demo_photos import make_photo, site_point, with_facts
from tests.backend.test_api_evidence import upload

S = tiny_scenario(1)


class CleanRepair:
    provider = "fake"

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        return RepairView(closed=True, patched=True, debris=False, confidence=0.95, note="")


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr(vision, "llm_and_model", lambda: (CleanRepair(), "vision-test-model"))


def _photo(scene: str, seed: int, work_id: str, day: int) -> bytes:
    lat, lon = site_point(S, work_id, 12)
    return with_facts(make_photo(scene, seed), lat, lon, datetime(2026, 11, day, 9, 0, tzinfo=INDIA))


W001_BEFORE = _photo("open", 1041, "W-001", 10)
W001_AFTER = _photo("patched", 1041, "W-001", 14)


def _w001_photos(client) -> None:
    assert upload(client, "W-001", "before", W001_BEFORE).status_code == 201
    assert upload(client, "W-001", "after", W001_AFTER).status_code == 201


def _checks(v: dict) -> dict[str, tuple[str, str]]:
    return {c["name"]: (c["status"], c["detail"]) for c in v["checks"]}


def _statuses(client) -> dict[str, str]:
    return {v["work"]["work_id"]: v["status"] for v in client.get("/works").json()}


def test_photos_then_a_resident_release_the_deposit(client, uploads_dir, fake_llm):
    _w001_photos(client)
    v = client.post("/works/W-001/verify").json()
    assert (v["verification_id"], v["result"], v["deposit_released"]) == ("V-0001", "pending", False)
    assert _checks(v)["resident"] == ("pending", "Asked on 14 Nov")
    assert _checks(v)["repair"] == ("ok", "Trench closed, surface patched, no debris")

    r = client.post("/reports/confirmation", json={"work_id": "W-001", "answer": "yes", "problems": []})
    assert r.status_code == 201
    assert (r.json()["report_id"], r.json()["kind"], r.json()["answer"]) == ("CR-0001", "confirmation", "yes")
    v = client.get("/works/W-001/verification").json()
    assert (v["verification_id"], v["result"], v["deposit_inr"], v["deposit_released"]) == ("V-0002", "verified", 200000, True)
    assert _statuses(client)["W-001"] == "verified"
    assert client.get("/works/W-001").json()["status"] == "verified"

    entries = list(reversed(client.get("/ledger").json()))
    actions = [e["action"] for e in entries if e["action"] != "scenario.loaded"]
    assert actions == ["evidence.added", "evidence.added", "verification.decided", "resident.confirmed",
                       "verification.decided", "deposit.released"]
    assert [e["summary"] for e in entries[-4:]] == ["W-001 waits for a resident to confirm",
                                                    "A resident confirmed the road is restored at W-001",
                                                    "Repair verified for W-001: every check passed",
                                                    "₹2,00,000 released to the contractor for W-001"]


def test_reused_photo_holds_the_money(client, uploads_dir, fake_llm):
    _w001_photos(client)
    upload(client, "T-001", "before", W001_BEFORE)
    upload(client, "T-001", "after", _photo("patched", 2301, "T-001", 14))
    v = client.post("/works/T-001/verify").json()
    assert (v["result"], v["deposit_released"]) == ("held", False)
    assert _checks(v)["reuse"] == ("fail", "Same as the before photo of W-001 (100% alike)")
    summaries = [e["summary"] for e in client.get("/ledger", params={"limit": 2}).json()]
    assert summaries == ["₹1,00,000 held for T-001; an inspector is called",
                         "Money held for T-001: Same as the before photo of W-001 (100% alike)"]
    assert _statuses(client)["T-001"] == "held"


def test_verify_needs_both_photos(client, uploads_dir, fake_llm):
    upload(client, "W-001", "before", W001_BEFORE)
    r = client.post("/works/W-001/verify")
    assert (r.status_code, r.json()["detail"]) == (422, "Add the before and after photos first.")
    assert client.get("/works/W-001/verification").json() == {"detail": "No check yet."}
    assert client.post("/works/W-999/verify").status_code == 404
    # an answer without both photos is recorded, but nothing is checked
    assert client.post("/reports/confirmation", json={"work_id": "W-001", "answer": "yes"}).status_code == 201
    assert client.get("/works/W-001/verification").status_code == 404


def test_not_yet_answer(client, uploads_dir):
    r = client.post("/reports/confirmation", json={"work_id": "W-001", "answer": "notyet", "problems": ["Still dug up"]})
    assert r.status_code == 201
    newest = client.get("/ledger", params={"limit": 1}).json()[0]
    assert (newest["actor"], newest["action"], newest["entity"]) == ("resident", "resident.not_yet", "work:W-001")
    assert newest["summary"] == "A resident says the road at W-001 is not restored yet: still dug up"


def test_bad_answers(client, uploads_dir):
    def post(**body):
        return client.post("/reports/confirmation", json={"work_id": "W-001", "answer": "yes", **body}).status_code

    assert post(answer="maybe") == 422
    assert post(problems=["a"] * 5) == 422
    assert post(problems=["x" * 61]) == 422
    assert post(name="Asha") == 201  # unknown fields are dropped, never stored
    assert post(work_id="W-999") == 404


def test_check_is_sent_live(client, uploads_dir, fake_llm):
    _w001_photos(client)
    with client.websocket_connect("/ws") as ws:
        client.post("/works/W-001/verify")
        for _ in range(5):
            msg = ws.receive_json()
            if msg["type"] == "verification.result":
                break
        else:
            raise AssertionError("no verification.result on /ws")
    assert (msg["data"]["verification_id"], msg["data"]["result"]) == ("V-0001", "pending")
