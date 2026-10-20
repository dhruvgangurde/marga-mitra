from sqlalchemy import select

from backend.app.db import session
from backend.app.tables import RunRow
from scripts.make_demo_photos import make_photo, with_facts
from tests.backend.test_api_plans import wait_for_run

HERE = {"lat": "13.0101", "lon": "74.7905"}  # 11 m from S-0001


def _report(client, category: str, photo: bytes | None = None, **form):
    files = {"photo": ("anything.jpg", photo, "image/jpeg")} if photo else None
    return client.post("/reports/emergency", data={"category": category, **HERE, **form}, files=files)


def _flag(client, work_id: str) -> dict:
    return next(f for f in client.get("/auditor/flags").json() if f["work_id"] == work_id)


def test_burst_pipe_becomes_an_emergency_work(client, uploads_dir):
    r = _report(client, "water", with_facts(make_photo("open", 7), None, None, None))
    assert r.status_code == 201
    report = r.json()
    assert (report["report_id"], report["kind"], report["work_id"]) == ("CR-0001", "emergency", "W-131")

    view = client.get("/works/W-131").json()
    w = view["work"]
    assert (view["status"], w["is_emergency"], w["dept"], w["road_name"], w["segment_ids"]) == (
        "emergency", True, "water", "Test Road", ["S-0001"])
    assert (w["requested_start"], w["latest_end"], w["deposit_inr"]) == (8, 9, 100000)

    [ev] = client.get("/works/W-131/evidence").json()
    assert (ev["kind"], ev["lat"], ev["lon"], report["photo_url"]) == ("citizen", 13.0101, 74.7905, ev["file_url"])

    entries = [(e["action"], e["actor"], e["summary"]) for e in reversed(client.get("/ledger").json())
               if e["action"].startswith("emergency.")]
    assert entries == [("emergency.reported", "resident", "Reported a burst water pipe on Test Road"),
                       ("emergency.allowed", "rules", "Emergency dig allowed at once: burst water pipe")]

    run = wait_for_run(client, "RUN-0001")
    assert run["status"] == "waiting_approval"
    with session() as s:
        assert s.scalar(select(RunRow.reason).where(RunRow.run_id == "RUN-0001")) == "emergency"

    flag = _flag(client, "W-131")
    assert (flag["severity"], flag["word"]) == ("warn", "Review needed")
    client.post(f"/approvals/{run['approval_id']}", json={"decision": "approve", "by": "ward_engineer"})
    reviewed = _flag(client, "W-131")
    assert (reviewed["flag_id"], reviewed["severity"], reviewed["word"]) == (flag["flag_id"], "ok", "Reviewed")


def test_cave_in_and_privacy(client):
    r = _report(client, "cavein", note="Call +91 98450 12345 on 2026-11-10 at 08:30")
    assert (r.json()["work_id"], client.get("/works/R-131").json()["work"]["dept"]) == ("R-131", "roads")
    assert r.json()["note"] == "Call [number removed] on 2026-11-10 at 08:30"
    assert r.json()["photo_url"] is None


def test_refuses_bad_reports(client):
    far = client.post("/reports/emergency", data={"category": "water", "lat": "13.5", "lon": "75.5"})
    assert (far.status_code, far.json()["detail"]) == (422, "This place is too far from the roads on the city map.")
    assert _report(client, "fire").status_code == 422
    assert _report(client, "water", b"not a photo").status_code == 422
    assert _report(client, "water", note="x" * 281).status_code == 422
    assert client.get("/works/W-131").status_code == 404
