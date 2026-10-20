import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.verify.decide import decide, distance_m, inspection_picked
from backend.app.verify.exif import INDIA
from backend.app.verify.phash import fingerprint
from contracts.fakes import tiny_scenario
from contracts.models import Assignment, CitizenReport, Evidence, Mode, VerificationCheck
from scripts.make_demo_photos import make_photo, site_point, with_facts

ROOT = Path(__file__).resolve().parents[2]
S = tiny_scenario(1)
WORKS = {w.work_id: w for w in S.works}
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
OK_REPAIR = VerificationCheck(name="repair", status="ok", detail="Trench closed, surface patched, no debris")
PRINTS = {
    ("open", 1041): fingerprint(with_facts(make_photo("open", 1041), None, None, None)),
    ("patched", 1041): fingerprint(with_facts(make_photo("patched", 1041), None, None, None)),
    ("patched", 2301): fingerprint(with_facts(make_photo("patched", 2301), None, None, None)),
}


def _photo(eid: str, work_id: str, kind: str, phash: str, day: int) -> Evidence:
    """A photo 12 m north of the work's site, taken at 09:00 India time on the given day of Nov."""
    lat, lon = site_point(S, work_id, 12)
    taken = datetime(2026, 11, day, 9, 0, tzinfo=INDIA)
    return Evidence(evidence_id=eid, work_id=work_id, kind=kind, file_url=f"http://x/files/{work_id}/{eid}.jpg",
                    lat=lat, lon=lon, taken_at=taken, phash=phash, uploaded_at=taken)


def _assignment(work_id: str) -> Assignment:
    w = WORKS[work_id]
    return Assignment(work_id=work_id, start_day=w.requested_start,
                      end_day=w.requested_start + w.modes[0].duration_days - 1, mode=Mode.open_cut)


def _yes(answer: str = "yes", day: int = 15, rid: str = "CR-0001", work_id: str = "W-001") -> CitizenReport:
    return CitizenReport(report_id=rid, kind="confirmation", work_id=work_id, answer=answer,
                         created_at=datetime(2026, 11, day, 10, 0, tzinfo=INDIA))


def _w001(**changes) -> list[Evidence]:
    before = _photo("E-0001", "W-001", "before", PRINTS["open", 1041], 10)
    after = _photo("E-0002", "W-001", "after", PRINTS["patched", 1041], 14)
    return [before, after.model_copy(update=changes)]


def _decide(work_id: str = "W-001", evidence: list[Evidence] | None = None, *, assignment="default", others=(),
            repair=OK_REPAIR, answers=None):
    return decide(work=WORKS[work_id], assignment=_assignment(work_id) if assignment == "default" else assignment,
                  evidence=_w001() if evidence is None else evidence, scenario=S, others=list(others), repair=repair,
                  answers=[_yes()] if answers is None else answers, verification_id="V-0001", now=NOW)


def _checks(v) -> dict[str, tuple[str, str]]:
    return {c.name: (c.status, c.detail) for c in v.checks}


def test_distance_m():
    assert round(distance_m((74.793, 13.010108), [[(74.792, 13.01), (74.794, 13.01)]])) == 12
    assert round(distance_m((74.791, 13.01), [[(74.792, 13.01)]])) == 108


def test_inspection_picked():
    assert inspection_picked("G-001") and inspection_picked("R-001")
    assert not any(inspection_picked(w) for w in ("W-001", "T-001", "W-104", "T-230"))


def test_all_good_is_verified():
    v = _decide()
    assert (v.result, v.deposit_released, v.deposit_inr, v.decided_at) == ("verified", True, 200000, NOW)
    assert _checks(v) == {
        "place": ("ok", "Both photos within 12 m of the site"),
        "time": ("ok", "Taken between 10 and 14 Nov"),
        "reuse": ("ok", "Not seen in any other work"),
        "repair": ("ok", "Trench closed, surface patched, no debris"),
        "resident": ("ok", "Confirmed the road is restored, 15 Nov"),
        "inspection": ("ok", "1 in 10 works is visited"),
    }


def test_no_answer_waits():
    v = _decide(answers=[])
    assert (v.result, v.deposit_released) == ("pending", False)
    assert _checks(v)["resident"] == ("pending", "Asked on 14 Nov")


def test_newest_answer_not_yet():
    v = _decide(answers=[_yes(day=15), _yes("notyet", day=16, rid="CR-0002")])
    assert v.result == "inspect"
    assert _checks(v)["resident"] == ("warn", "A resident says the road is not restored yet")


@pytest.mark.parametrize("status", ["warn", "pending"])
def test_unsure_repair_needs_an_inspector(status):
    assert _decide(repair=VerificationCheck(name="repair", status=status, detail="x")).result == "inspect"


def test_far_photo_is_held():
    v = _decide(evidence=_w001(lat=13.0226, lon=74.80))
    assert (v.result, v.deposit_released) == ("held", False)
    assert _checks(v)["place"] == ("fail", "The after photo was taken 1.5 km from the site")


def test_late_photo_is_held():
    v = _decide(evidence=_w001(taken_at=datetime(2026, 11, 20, 9, 0, tzinfo=INDIA)))
    assert v.result == "held"
    assert _checks(v)["time"] == ("fail", "The after photo was taken on 20 Nov, outside the work dates")


def test_reused_photo_is_held():
    w001_before, w001_after = _w001()
    t001 = [_photo("E-0003", "T-001", "before", PRINTS["open", 1041], 12),
            _photo("E-0004", "T-001", "after", PRINTS["patched", 2301], 14)]
    v = _decide("T-001", t001, others=[w001_before, w001_after], answers=[_yes(work_id="T-001")])
    assert v.result == "held"
    assert _checks(v)["reuse"] == ("fail", "Same as the before photo of W-001 (100% alike)")


def test_own_photo_is_not_reuse():
    copy = _w001()[0].model_copy(update={"evidence_id": "E-0009"})
    assert _checks(_decide(others=[copy]))["reuse"] == ("ok", "Not seen in any other work")


def test_resident_photo_is_named():
    resident = _photo("E-0009", "T-001", "citizen", PRINTS["patched", 1041], 14)
    assert _checks(_decide(others=[resident]))["reuse"] == ("fail", "Same as a resident's photo of T-001 (100% alike)")


def test_picked_work_needs_an_inspector():
    g = [_photo("E-0001", "G-001", "before", PRINTS["open", 1041], 11),
         _photo("E-0002", "G-001", "after", PRINTS["patched", 1041], 14)]
    v = _decide("G-001", g, answers=[_yes(work_id="G-001")])
    assert v.result == "inspect"
    assert _checks(v)["inspection"] == ("pending", "Picked for a visit: an inspector comes within 2 days")


def test_photo_without_location():
    v = _decide(evidence=_w001(lat=None, lon=None))
    assert v.result == "inspect"
    assert _checks(v)["place"] == ("warn", "The after photo has no location")


def test_only_a_before_photo():
    v = _decide(evidence=_w001()[:1])
    assert (v.result, v.deposit_released) == ("pending", False)
    assert all(c.status == "pending" and c.detail == "Waiting for the after photo" for c in v.checks)
    assert [c.name for c in v.checks] == ["place", "time", "reuse", "repair", "resident", "inspection"]


def test_only_an_after_photo():
    v = _decide(evidence=_w001()[1:])
    assert _checks(v)["place"] == ("ok", "The after photo is within 12 m of the site")


def test_newest_photos_are_used():
    old_after = _photo("E-0000", "W-001", "after", PRINTS["patched", 1041], 20)
    old_after = old_after.model_copy(update={"uploaded_at": datetime(2026, 11, 1, tzinfo=UTC)})
    assert _decide(evidence=[old_after, *_w001()]).result == "verified"


def test_repair_left_out():
    v = decide(work=WORKS["W-001"], assignment=_assignment("W-001"), evidence=_w001(), scenario=S, others=[],
               answers=[_yes()])
    assert v.result == "inspect"
    assert _checks(v)["repair"] == ("pending", "A person will check the repair")
    assert v.verification_id == "V-0000"


def test_requested_days_without_assignment():
    assert _checks(_decide(assignment=None))["time"] == ("ok", "Taken between 10 and 14 Nov")


def test_decide_stays_pure():
    code = ("import backend.app.verify.decide, sys; "
            "assert not {'backend.app.config', 'backend.app.db', 'backend.app.store'} & set(sys.modules)")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
