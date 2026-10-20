"""The money decision: six checks on a work's photos and answers, then verified, held, inspect or pending.

Pure: imports only contracts, the standard library and the fingerprint helpers. The evaluation (evals/) calls decide()
to count caught fake repairs, so keep its keyword signature.
"""
import hashlib
import math
from datetime import UTC, date, datetime, timedelta, timezone

from backend.app.verify.phash import alike_percent, distance
from contracts import costs
from contracts.models import Assignment, CitizenReport, Evidence, Scenario, Verification, VerificationCheck, Work

INDIA = timezone(timedelta(hours=5, minutes=30))
EARTH_RADIUS_M = 6_371_000
CHECK_NAMES = ("place", "time", "reuse", "repair", "resident", "inspection")


def _rules() -> dict:
    return costs.policy()["verification"]


def _piece_m(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_m(point: tuple[float, float], lines: list[list[tuple[float, float]]]) -> float:
    """Metres from a (lon, lat) point to the nearest piece of any line, in a flat projection around the point."""
    lon0, lat0 = point
    scale = math.cos(math.radians(lat0))

    def xy(p: tuple[float, float]) -> tuple[float, float]:
        return (math.radians(p[0] - lon0) * EARTH_RADIUS_M * scale, math.radians(p[1] - lat0) * EARTH_RADIUS_M)

    best = math.inf
    for line in lines:
        pts = [xy(p) for p in line]
        for a, b in zip(pts, pts[1:] or pts, strict=False):  # a one-point line is measured as a point
            best = min(best, _piece_m(0.0, 0.0, *a, *b))
    return best


def inspection_picked(work_id: str) -> bool:
    """A fixed share of works is visited; the pick depends only on the work id, so it is the same every time."""
    draw = int(hashlib.sha256(work_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return draw < _rules()["random_inspection_rate"]


def _day(d: date) -> str:
    return f"{d.day} {d:%b}"


def _between(d0: date, d1: date) -> str:
    if (d0.year, d0.month) == (d1.year, d1.month):
        return f"{d0.day} and {_day(d1)}"
    return f"{_day(d0)} and {_day(d1)}"


def _india_date(t: datetime) -> date:
    return t.astimezone(INDIA).date()


def _distance_words(d: float) -> str:
    return f"{d / 1000:.1f} km" if d >= 1000 else f"{round(d)} m"


def _newest(evidence: list[Evidence], kind: str) -> Evidence | None:
    of_kind = sorted((e for e in evidence if e.kind == kind), key=lambda e: (e.uploaded_at, e.evidence_id))
    return of_kind[-1] if of_kind else None


def _check(name: str, status: str, detail: str) -> VerificationCheck:
    return VerificationCheck(name=name, status=status, detail=detail)


def _place(photos: list[Evidence], lines: list[list[tuple[float, float]]]) -> VerificationCheck:
    for p in photos:
        if p.lat is None or p.lon is None:
            return _check("place", "warn", f"The {p.kind} photo has no location")
    far, d = max(((p, distance_m((p.lon, p.lat), lines)) for p in photos), key=lambda x: x[1])
    if d > _rules()["place_max_m"]:
        return _check("place", "fail", f"The {far.kind} photo was taken {_distance_words(d)} from the site")
    if len(photos) == 1:
        return _check("place", "ok", f"The after photo is within {round(d)} m of the site")
    return _check("place", "ok", f"Both photos within {round(d)} m of the site")


def _time(photos: list[Evidence], first: date, last: date) -> VerificationCheck:
    slack = timedelta(days=_rules()["time_slack_days"])
    for p in photos:
        if p.taken_at is None:
            return _check("time", "warn", f"The {p.kind} photo has no time")
    for p in photos:
        taken = _india_date(p.taken_at)
        if not first - slack <= taken <= last + slack:
            return _check("time", "fail", f"The {p.kind} photo was taken on {_day(taken)}, outside the work dates")
    return _check("time", "ok", f"Taken between {_between(first, last)}")


def _reuse(photos: list[Evidence], others: list[Evidence], work_id: str) -> VerificationCheck:
    limit = _rules()["phash_max_distance"]
    matches = [(distance(p.phash, o.phash), o.uploaded_at, o.evidence_id, o)
               for o in others if o.work_id != work_id for p in photos]
    close = [m for m in matches if m[0] <= limit]
    if not close:
        return _check("reuse", "ok", "Not seen in any other work")
    d, _, _, o = min(close, key=lambda m: m[:3])
    whose = f"a resident's photo of {o.work_id}" if o.kind == "citizen" else f"the {o.kind} photo of {o.work_id}"
    return _check("reuse", "fail", f"Same as {whose} ({alike_percent(d)}% alike)")


def _resident(answers: list[CitizenReport], work_id: str, after: Evidence) -> VerificationCheck:
    mine = sorted((a for a in answers if a.kind == "confirmation" and a.work_id == work_id),
                  key=lambda a: (a.created_at, a.report_id), reverse=True)
    yes = [a for a in mine if a.answer == "yes"]
    if mine and mine[0].answer == "notyet":
        return _check("resident", "warn", "A resident says the road is not restored yet")
    if mine and len(yes) >= _rules()["resident_confirmations_needed"]:
        return _check("resident", "ok", f"Confirmed the road is restored, {_day(_india_date(yes[0].created_at))}")
    asked = _india_date(after.taken_at or after.uploaded_at)
    return _check("resident", "pending", f"Asked on {_day(asked)}")


def _inspection(work_id: str) -> VerificationCheck:
    if inspection_picked(work_id):
        return _check("inspection", "pending", "Picked for a visit: an inspector comes within 2 days")
    return _check("inspection", "ok", "1 in 10 works is visited")


def _result(checks: dict[str, VerificationCheck]) -> str:
    if any(checks[n].status == "fail" for n in ("place", "time", "reuse", "repair")):
        return "held"
    if (any(c.status == "warn" for c in checks.values()) or checks["repair"].status == "pending"
            or checks["inspection"].status == "pending"):
        return "inspect"
    if checks["resident"].status == "pending":
        return "pending"
    return "verified"


def decide(*, work: Work, assignment: Assignment | None, evidence: list[Evidence], scenario: Scenario,
           others: list[Evidence], repair: VerificationCheck | None = None, answers: list[CitizenReport] | None = None,
           verification_id: str = "V-0000", now: datetime | None = None) -> Verification:
    before, after = _newest(evidence, "before"), _newest(evidence, "after")
    if after is None:
        checks = {n: _check(n, "pending", "Waiting for the after photo") for n in CHECK_NAMES}
        result = "pending"
    else:
        start, end = ((assignment.start_day, assignment.end_day) if assignment
                      else (work.requested_start, work.requested_start + work.modes[0].duration_days - 1))
        segments = {s.segment_id: s for s in scenario.segments}
        lines = [segments[sid].coords for sid in work.segment_ids if sid in segments]
        photos = [p for p in (before, after) if p is not None]
        checks = {
            "place": _place(photos, lines),
            "time": _time(photos, scenario.start_date + timedelta(days=start), scenario.start_date + timedelta(days=end)),
            "reuse": _reuse(photos, others, work.work_id),
            "repair": repair or _check("repair", "pending", "A person will check the repair"),
            "resident": _resident(answers or [], work.work_id, after),
            "inspection": _inspection(work.work_id),
        }
        result = _result(checks)
    return Verification(verification_id=verification_id, work_id=work.work_id, result=result,
                        checks=[checks[n] for n in CHECK_NAMES], deposit_inr=work.deposit_inr,
                        deposit_released=result == "verified", decided_at=now or datetime.now(UTC))
