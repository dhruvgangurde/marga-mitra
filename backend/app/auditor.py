"""The auditor: four rules that flag odd patterns in plans, photos and the record. find_flags is pure."""
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from fastapi import FastAPI
from pydantic import ValidationError

from backend.app import store
from backend.app.config import get_settings
from backend.app.db import session
from backend.app.deps import in_session
from backend.app.ids import next_id
from backend.app.verify.phash import distance
from backend.app.words import clock, day_label, dept_name
from contracts.models import (
    Approval,
    AuditorFlag,
    Evidence,
    LedgerEntry,
    Plan,
    PolicyResult,
    Scenario,
    Verification,
    WsEvent,
)

logger = logging.getLogger(__name__)

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


def load_inputs(seed: int, today_day: int) -> AuditInputs:
    with session() as s:
        scenario = store.get_scenario(s, seed)
        plans = store.list_plans(s, seed)
        ids = {p.plan_id for p in plans}
        return AuditInputs(
            scenario=scenario, plans=plans, verifications=store.latest_verifications(s, seed),
            evidence=store.all_evidence(s, seed), approvals=[a for a in store.list_approvals(s) if a.plan_id in ids],
            entries=store.entries_by_action(s, ["emergency.allowed", "rules.checked"]),
            today=scenario.start_date + timedelta(days=today_day))


async def _raise(app: FastAPI, seed: int, f: Finding) -> AuditorFlag | None:
    """Record, store and send one finding; None when the stored flag already says the same."""
    key = f"{f.rule}:{f.subject}"
    old = await asyncio.to_thread(in_session, store.get_flag, seed, key)
    if old and (old.severity, old.word, old.text) == (f.severity, f.word, f.text):
        return None
    flag_id = old.flag_id if old else await asyncio.to_thread(in_session, next_id, "F")
    deps = app.state.wiring.deps
    entry = await deps.ledger_append("auditor", "auditor.flag", f.entity, f.headline,
                                     {"flag_id": flag_id, "rule": f.rule, "severity": f.severity, "word": f.word,
                                      "work_id": f.work_id, "text": f.text})
    flag = AuditorFlag(flag_id=flag_id, severity=f.severity, word=f.word, work_id=f.work_id, text=f.text,
                       ledger_seq=entry.seq, created_at=entry.ts)
    await asyncio.to_thread(in_session, store.save_flag, seed, key, f.rule, flag)
    await deps.emit(WsEvent(type="auditor.flag", data=flag.model_dump(mode="json"), ts=datetime.now(UTC)))
    return flag


async def audit(app: FastAPI) -> list[AuditorFlag]:
    """Run the four rules on the active test case; returns the flags that are new or changed."""
    async with app.state.audit_lock:
        seed = app.state.seed
        x = await asyncio.to_thread(load_inputs, seed, get_settings().today_day)
        raised = [await _raise(app, seed, f) for f in find_flags(x)]
        return [f for f in raised if f]


async def safe_audit(app: FastAPI) -> None:
    """The auditor never stops the action that started it."""
    try:
        await audit(app)
    except Exception:  # any failure here must leave the plan, approval or photo check as it is
        logger.exception("The auditor could not run.")
