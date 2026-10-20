import math
from collections import Counter
from datetime import timedelta
from itertools import combinations

from contracts.fakes import tiny_scenario
from contracts.models import Verification, VerificationCheck
from evals import fake_repairs
from evals.fake_repairs import INDIA, FakeRepairResult, build_cases, count_caught

TARGETS = {"reused": "reuse", "far": "place", "late": "time", "genuine": None}
SEGMENTS = {s.segment_id: s for s in tiny_scenario().segments}


def bits(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def metres(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    return math.hypot((lon2 - lon1) * 111_320 * math.cos(math.radians(lat1)), (lat2 - lat1) * 111_320)


def after(case):
    return next(e for e in case.evidence if e.kind == "after")


def work_dates(case):
    start = tiny_scenario().start_date
    return start + timedelta(days=case.assignment.start_day), start + timedelta(days=case.assignment.end_day)


def test_the_twelve_cases():
    cases = build_cases()
    assert Counter(c.kind for c in cases) == {"reused": 4, "far": 3, "late": 3, "genuine": 2}
    assert all(c.target == TARGETS[c.kind] for c in cases)
    assert all(after(c).phash in {o.phash for o in c.others} for c in cases if c.kind == "reused")


def test_photo_ids_are_unique_and_far_apart():
    photos = {e.evidence_id: e.phash for c in build_cases() for e in c.evidence + c.others
              if not (c.kind == "reused" and e.kind == "after")}
    ids = list(photos.values())
    assert len(ids) == len(set(ids))
    assert min(bits(a, b) for a, b in combinations(ids, 2)) >= 20


def test_far_photos_are_far_from_the_work():
    for c in build_cases():
        if c.kind == "far":
            p = after(c)
            points = [pt for s in c.work.segment_ids for pt in SEGMENTS[s].coords]
            assert min(metres(lon, lat, p.lon, p.lat) for lon, lat in points) >= 500, c.name


def test_late_photos_are_outside_the_work_days():
    for c in build_cases():
        if c.kind == "late":
            first, last = work_dates(c)
            taken = after(c).taken_at.astimezone(INDIA).date()
            assert taken <= first - timedelta(days=3) or taken >= last + timedelta(days=3), c.name


def stand_in_decide(*, work, assignment, evidence, scenario, others) -> Verification:
    start = scenario.start_date
    first, last = start + timedelta(days=assignment.start_day), start + timedelta(days=assignment.end_day)
    points = [pt for s in work.segment_ids for pt in SEGMENTS[s].coords]
    photo = next(e for e in evidence if e.kind == "after")
    reused = any(bits(photo.phash, o.phash) <= 8 for o in others)
    far = any(min(metres(lon, lat, e.lon, e.lat) for lon, lat in points) > 50 for e in evidence)
    late = any(not first - timedelta(days=2) <= e.taken_at.astimezone(INDIA).date() <= last + timedelta(days=2)
               for e in evidence)
    status = {"reuse": reused, "place": far, "time": late}
    checks = [VerificationCheck(name=n, status="fail" if status.get(n) else "ok", detail="")
              for n in ("place", "time", "reuse", "repair", "resident", "inspection")]
    return Verification(verification_id="V-0", work_id=work.work_id, result="held", checks=checks, deposit_inr=0,
                        deposit_released=False, decided_at=photo.uploaded_at)


def all_ok(**kwargs) -> Verification:
    v = stand_in_decide(**kwargs)
    return v.model_copy(update={"checks": [c.model_copy(update={"status": "ok"}) for c in v.checks]})


def test_a_working_check_catches_every_fake():
    assert count_caught(stand_in_decide) == FakeRepairResult(caught=10, total=10, genuine_passed=2, genuine_total=2,
                                                             note="")


def test_a_check_that_passes_everything_catches_nothing():
    r = count_caught(all_ok)
    assert (r.caught, r.total, r.genuine_passed) == (0, 10, 2)


def test_no_photo_checks_yet():
    assert count_caught(None) == FakeRepairResult(0, 0, 0, 0, "The photo checks are not merged yet.")


def test_a_broken_check_counts_as_not_caught():
    def broken(**kwargs):
        raise RuntimeError("boom")

    r = count_caught(broken)
    assert r.caught == 0 and r.genuine_passed == 0
    assert "RuntimeError" in r.note


def test_load_decide_is_none_before_the_photo_checks_merge(monkeypatch):
    monkeypatch.setattr(fake_repairs, "optional", lambda module, name: None)
    assert fake_repairs.load_decide() is None
