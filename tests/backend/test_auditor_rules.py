from datetime import UTC, date, datetime, timedelta

from backend.app.auditor import AuditInputs, find_flags
from backend.app.words import date_words, metres
from contracts.fakes import tiny_scenario
from contracts.models import (
    Approval,
    Assignment,
    Evidence,
    LedgerEntry,
    Plan,
    PolicyResult,
    RuleCheck,
    Verification,
    VerificationCheck,
)

S = tiny_scenario(1)
T = datetime(2026, 11, 10, 3, 44, tzinfo=UTC)
A, B = "ffffffffffffffff", "0000000000000000"
W131 = S.works[0].model_copy(update={"work_id": "W-131", "is_emergency": True})


def inputs(**kw) -> AuditInputs:
    base = {"scenario": S, "plans": [], "verifications": {}, "evidence": [], "approvals": [], "entries": [],
            "today": date(2026, 11, 10)}
    return AuditInputs(**{**base, **kw})


def photo(eid: str, wid: str, kind: str, phash: str) -> Evidence:
    return Evidence(evidence_id=eid, work_id=wid, kind=kind, file_url=f"http://x/{eid}.jpg", phash=phash, uploaded_at=T)


def held(wid: str, detail: str) -> dict[str, Verification]:
    return {wid: Verification(verification_id="V-0001", work_id=wid, result="held", deposit_inr=10000,
                              checks=[VerificationCheck(name="reuse", status="fail", detail=detail)],
                              deposit_released=False, decided_at=T)}


def plan(pid: str, status: str, at: datetime, *days: tuple[str, int, int]) -> Plan:
    return Plan(plan_id=pid, seed=1, variant="orchestrated", status=status, created_at=at,
                assignments=[Assignment(work_id=w, start_day=s, end_day=e, mode="open_cut") for w, s, e in days])


def entry(seq: int, action: str, entity: str, payload: dict) -> LedgerEntry:
    return LedgerEntry(seq=seq, ts=T, actor="rules", action=action, entity=entity, summary="", payload=payload,
                       prev_hash="0" * 64, hash="0" * 64)


def texts(x: AuditInputs, rule: str) -> list[str]:
    return [f.text for f in find_flags(x) if f.rule == rule]


def test_photo_reused():
    photos = [photo("E-0001", "W-001", "before", A), photo("E-0002", "T-001", "before", A),
              photo("E-0003", "T-001", "after", B)]
    x = inputs(evidence=photos, verifications=held("T-001", "Same as the before photo of W-001 (100% alike)"))
    [f] = find_flags(x)
    assert (f.rule, f.subject, f.severity, f.word, f.work_id, f.entity) == (
        "photo_reused", "T-001", "fail", "Photo reused", "T-001", "work:T-001")
    assert f.text == ("The before photo of T-001 is the same as the before photo of W-001 (100% alike). "
                      "Money is held and an inspector visits on 12 Nov.")
    assert f.headline == "Photo reused at T-001: money stays held"
    assert texts(inputs(verifications=x.verifications), "photo_reused") == [
        "A photo of T-001 is the same as the before photo of W-001 (100% alike). "
        "Money is held and an inspector visits on 12 Nov."]
    assert texts(inputs(verifications=held("T-001", "Seen before")), "photo_reused") == [
        "A photo of T-001 was used before for another work. Money is held and an inspector visits on 12 Nov."]


def test_moved_twice():
    first = plan("P-0001", "waiting_approval", T, ("G-001", 12, 15))
    second = plan("P-0002", "waiting_approval", T + timedelta(hours=1), ("G-001", 14, 17))
    [f] = find_flags(inputs(plans=[first, second]))
    assert (f.rule, f.severity, f.word, f.headline) == ("moved_twice", "warn", "Look again", "G-001 was moved twice in 3 days")
    assert f.text == "Gas work G-001 was moved twice in 3 days. Ask the Gas department if its crew is free on 16 Nov."
    assert find_flags(inputs(plans=[first, second.model_copy(update={"created_at": T + timedelta(days=4)})])) == []
    assert find_flags(inputs(plans=[first, second.model_copy(update={"status": "rejected"})])) == []


def test_emergency_review():
    s = S.model_copy(update={"works": [*S.works, W131]})
    allowed = [entry(1, "emergency.allowed", "work:W-131", {})]
    p = plan("P-0001", "approved", T, ("W-131", 8, 9))
    review = Approval(approval_id="A-0001", plan_id="P-0001", run_id="RUN-0001", tier="ward_engineer", status="approved",
                      summary="New plan", requested_at=T, decided_at=datetime(2026, 11, 10, 4, 10, tzinfo=UTC),
                      decided_by="ward_engineer")
    [f] = find_flags(inputs(scenario=s, entries=allowed))
    assert (f.severity, f.word, f.headline) == ("warn", "Review needed", "Emergency dig W-131 waits for a review")
    assert f.text == ("Emergency dig W-131 started before approval, as the rules allow. "
                      "The ward engineer has not reviewed it yet.")
    [f] = find_flags(inputs(scenario=s, entries=allowed, plans=[p], approvals=[review]))
    assert (f.severity, f.word, f.headline) == ("ok", "Reviewed", "Emergency dig W-131 was reviewed")
    assert f.text.endswith("The ward engineer reviewed it at 09:40.")
    early = review.model_copy(update={"decided_at": T - timedelta(minutes=5)})
    assert [f.word for f in find_flags(inputs(scenario=s, entries=allowed, plans=[p], approvals=[early]))] == ["Review needed"]


def test_approved_with_warning():
    rain = "W-001 have an open trench during Heavy rain, 14–15 Nov"
    checks = [RuleCheck(name="protected_roads", severity="ok", detail="No protected road is dug"),
              RuleCheck(name="rain", severity="warn", detail=rain)]
    result = PolicyResult(plan_id="P-0003", passed=True, checks=checks, tier="ward_engineer", works_changed=1,
                          cost_delta_inr=0)
    p = plan("P-0003", "approved", T)
    [f] = find_flags(inputs(plans=[p], entries=[entry(1, "rules.checked", "plan:P-0003", result.model_dump(mode="json"))]))
    assert (f.subject, f.work_id, f.entity, f.headline) == (
        "P-0003", None, "plan:P-0003", "Plan P-0003 was approved with a warning")
    assert f.text == (f"Plan P-0003 was approved while the rules check said: {rain}. "
                      "Look at it again before the work starts.")
    fine = result.model_copy(update={"checks": checks[:1]})
    assert find_flags(inputs(plans=[p], entries=[entry(1, "rules.checked", "plan:P-0003", fine.model_dump(mode="json"))])) == []


def test_words():
    assert (metres(620), metres(1100), date_words(date(2029, 3, 3))) == ("620 m", "1.1 km", "3 Mar 2029")
