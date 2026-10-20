from datetime import datetime

from sqlalchemy import select

from backend.app.db import session
from backend.app.tables import EvidenceRow
from backend.app.verify.exif import INDIA
from contracts.fakes import tiny_scenario
from scripts.make_demo_photos import make_photo, site_point, with_facts

LAT, LON = site_point(tiny_scenario(1), "W-001", 12)


def upload(client, work_id: str, kind: str, data: bytes, **form):
    return client.post(f"/works/{work_id}/evidence", data={"kind": kind, **form},
                       files={"photo": ("anything.jpg", data, "image/jpeg")})


def _facts_of(evidence_id: str) -> tuple[str, str]:
    with session() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.evidence_id == evidence_id)).one()
        return row.place_from, row.time_from


def test_upload_with_facts_in_the_photo(client, uploads_dir):
    data = with_facts(make_photo("open", 1041), LAT, LON, datetime(2026, 11, 10, 8, 12, tzinfo=INDIA))
    r = upload(client, "W-001", "before", data)
    assert r.status_code == 201
    ev = r.json()
    assert (ev["evidence_id"], ev["work_id"], ev["kind"], ev["lat"], ev["lon"]) == ("E-0001", "W-001", "before", LAT, LON)
    assert ev["taken_at"] == "2026-11-10T08:12:00+05:30"
    assert ev["file_url"].endswith("/files/W-001/E-0001.jpg")
    assert len(ev["phash"]) == 16
    assert client.get("/files/W-001/E-0001.jpg").content == data
    assert _facts_of("E-0001") == ("photo", "photo")
    newest = client.get("/ledger", params={"limit": 1}).json()[0]
    assert (newest["action"], newest["actor"], newest["entity"]) == ("evidence.added", "water", "work:W-001")
    assert newest["summary"] == "Water crew added the before photo for W-001"
    assert newest["payload"] == ev


def test_facts_from_the_phone(client, uploads_dir):
    data = with_facts(make_photo("patched", 1041), None, None, None)
    r = upload(client, "W-001", "after", data, lat=str(LAT), lon=str(LON), taken_at="2026-11-14T09:40:00")
    ev = r.json()
    assert (ev["lat"], ev["lon"], ev["taken_at"]) == (LAT, LON, "2026-11-14T09:40:00+05:30")
    assert _facts_of(ev["evidence_id"]) == ("phone", "phone")


def test_photo_facts_win_over_the_phone(client, uploads_dir):
    data = with_facts(make_photo("open", 1041), LAT, LON, None)
    ev = upload(client, "W-001", "before", data, lat="1", lon="2", taken_at="2026-11-10T08:00:00+05:30").json()
    assert (ev["lat"], ev["lon"], ev["taken_at"]) == (LAT, LON, "2026-11-10T08:00:00+05:30")
    assert _facts_of(ev["evidence_id"]) == ("photo", "phone")


def test_no_facts_at_all(client, uploads_dir):
    ev = upload(client, "W-001", "citizen", with_facts(make_photo("open", 1041), None, None, None)).json()
    assert (ev["lat"], ev["lon"], ev["taken_at"]) == (None, None, None)
    assert _facts_of(ev["evidence_id"]) == ("none", "none")
    newest = client.get("/ledger", params={"limit": 1}).json()[0]
    assert (newest["actor"], newest["summary"]) == ("resident", "A resident added a photo for W-001")


def test_bad_uploads(client, uploads_dir):
    r = upload(client, "W-001", "before", b"just some text")
    assert (r.status_code, r.json()["detail"]) == (422, "The photo must be a JPEG or PNG file.")
    r = upload(client, "W-001", "before", b"\xff\xd8\xff" + b"\0" * (9 * 1024 * 1024))
    assert (r.status_code, r.json()["detail"]) == (422, "The photo is larger than 8 MB.")
    r = upload(client, "W-999", "before", with_facts(make_photo("open", 1041), None, None, None))
    assert (r.status_code, r.json()["detail"]) == (404, "Unknown work.")
    assert upload(client, "W-001", "during", with_facts(make_photo("open", 1041), None, None, None)).status_code == 422
    assert client.get("/works/W-999/evidence").status_code == 404


def test_list_oldest_first(client, uploads_dir):
    for kind, scene in (("before", "open"), ("after", "patched"), ("citizen", "patched")):
        upload(client, "W-001", kind, with_facts(make_photo(scene, 1041), None, None, None))
    listed = client.get("/works/W-001/evidence").json()
    assert [(e["evidence_id"], e["kind"]) for e in listed] == [("E-0001", "before"), ("E-0002", "after"),
                                                               ("E-0003", "citizen")]
    assert client.get("/works/T-001/evidence").json() == []
