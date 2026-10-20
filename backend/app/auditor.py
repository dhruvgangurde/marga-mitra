"""The auditor: four rules that flag odd patterns in plans, photos and the record. find_flags is pure."""
import re
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import ValidationError

from backend.app.verify.phash import distance
from backend.app.words import clock, day_label, dept_name
from contracts.models import Approval, Evidence, LedgerEntry, Plan, PolicyResult, Scenario, Verification

REUSED = re.compile(r"^Same as (the (before|after) photo|a resident's photo) of (\S+) \((\d+)% alike\)$")
MOVES_WITHIN = timedelta(days=3)
PLANS_THAT_MOVE = {"waiting_approval", "approved", "superseded"}


@dataclass
class AuditInputs:
    scenario: Scenario
    plans: list[Plan]  # all of the seed's, any status
    verifications: dict[str, Verification]  # newest per work id
    evidence: list[Evidence]  # all of the seed's photos
    approvals: list[Approval]
    entries: list[LedgerEntry]  # emergency.allowed and rules.checked, oldest first
    today: date


@dataclass
class Finding:
    rule: str
    subject: str  # a work or plan id
    severity: str
    word: str
    work_id: str | None
    text: str
    headline: str  # the record summary
    entity: str


def _newest(evidence: list[Evidence], work_id: str, kind: str) -> Evidence | None:
    mine = [e for e in evidence if e.work_id == work_id and e.kind == kind]
    return max(mine, key=lambda e: (e.uploaded_at, e.evidence_id), default=None)


def _own_kind(x: AuditInputs, work_id: str, other_id: str, other_kind: str) -> str | None:
    """Which of the work's newest before and after photos is closer to the other work's photo; a tie gives after."""
    theirs = [e.phash for e in x.evidence if e.work_id == other_id and e.kind == other_kind]
    best: tuple[int, str] | None = None
    for kind in ("after", "before"):
        own = _newest(x.evidence, work_id, kind)
        if own is None or not theirs:
            continue
        d = min(distance(own.phash, t) for t in theirs)
        if best is None or d < best[0]:
            best = (d, kind)
    return best[1] if best else None


def _photo_reused(x: AuditInputs) -> list[Finding]:
    out = []
    for wid, v in sorted(x.verifications.items()):
        reuse = next((c for c in v.checks if c.name == "reuse"), None)
        if v.result != "held" or reuse is None or reuse.status != "fail":
            continue
        tail = f"Money is held and an inspector visits on {day_label(x.today, 2)}."
        m = REUSED.match(reuse.detail)
        if m is None:
            text = f"A photo of {wid} was used before for another work. {tail}"
        else:
            whose, kind, other, pct = m.groups()
            own = _own_kind(x, wid, other, kind or "citizen")
            lead = f"The {own} photo of {wid}" if own else f"A photo of {wid}"
            text = f"{lead} is the same as {whose} of {other} ({pct}% alike). {tail}"
        out.append(Finding("photo_reused", wid, "fail", "Photo reused", wid, text,
                           f"Photo reused at {wid}: money stays held", f"work:{wid}"))
    return out


def _moved_twice(x: AuditInputs) -> list[Finding]:
    plans = sorted((p for p in x.plans if p.status in PLANS_THAT_MOVE), key=lambda p: (p.created_at, p.plan_id))
    out = []
    for w in sorted(x.scenario.works, key=lambda w: w.work_id):
        if w.done or w.is_emergency:
            continue
        days = (w.requested_start, w.requested_start + w.modes[0].duration_days - 1)
        changes = []
        for p in plans:
            a = next((a for a in p.assignments if a.work_id == w.work_id), None)
            if a is None:
                continue
            if (a.start_day, a.end_day) != days:
                changes.append(p.created_at)
            days = (a.start_day, a.end_day)
        if any(b - a <= MOVES_WITHIN for a, b in zip(changes, changes[1:], strict=False)):
            name = dept_name(w.dept)
            out.append(Finding(
                "moved_twice", w.work_id, "warn", "Look again", w.work_id,
                f"{name} work {w.work_id} was moved twice in 3 days. Ask the {name} department if its crew is free on "
                f"{day_label(x.scenario.start_date, days[0])}.",
                f"{w.work_id} was moved twice in 3 days", f"work:{w.work_id}"))
    return out


def _emergency_review(x: AuditInputs) -> list[Finding]:
    works = {w.work_id for w in x.scenario.works}
    plans = {p.plan_id: p for p in x.plans}
    allowed = {wid: e for e in x.entries if e.action == "emergency.allowed"
               and (wid := e.entity.removeprefix("work:")) in works}
    out = []
    for wid, entry in sorted(allowed.items()):
        reviews = [a for a in x.approvals
                   if a.status in ("approved", "rejected") and a.decided_by == "ward_engineer" and a.decided_at
                   and a.decided_at > entry.ts and a.plan_id in plans
                   and any(s.work_id == wid for s in plans[a.plan_id].assignments)]
        lead = f"Emergency dig {wid} started before approval, as the rules allow."
        if reviews:
            first = min(reviews, key=lambda a: (a.decided_at, a.approval_id))
            out.append(Finding("emergency_review", wid, "ok", "Reviewed", wid,
                               f"{lead} The ward engineer reviewed it at {clock(first.decided_at)}.",
                               f"Emergency dig {wid} was reviewed", f"work:{wid}"))
        else:
            out.append(Finding("emergency_review", wid, "warn", "Review needed", wid,
                               f"{lead} The ward engineer has not reviewed it yet.",
                               f"Emergency dig {wid} waits for a review", f"work:{wid}"))
    return out


def _approved_with_warning(x: AuditInputs) -> list[Finding]:
    checked = {e.entity: e for e in x.entries if e.action == "rules.checked"}  # oldest first, so the newest wins
    out = []
    for p in sorted(x.plans, key=lambda p: p.plan_id):
        entry = checked.get(f"plan:{p.plan_id}")
        if p.status not in ("approved", "superseded") or entry is None:
            continue
        try:
            result = PolicyResult.model_validate(entry.payload)
        except ValidationError:
            continue
        bad = next((c for c in result.checks if c.severity != "ok"), None)
        if bad:
            out.append(Finding(
                "approved_with_warning", p.plan_id, "warn", "Look again", None,
                f"Plan {p.plan_id} was approved while the rules check said: {bad.detail.rstrip('.')}. "
                "Look at it again before the work starts.",
                f"Plan {p.plan_id} was approved with a warning", f"plan:{p.plan_id}"))
    return out


def find_flags(x: AuditInputs) -> list[Finding]:
    return [*_photo_reused(x), *_moved_twice(x), *_emergency_review(x), *_approved_with_warning(x)]
