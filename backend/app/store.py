"""Database reads and writes. Every function takes a Session first and returns contract models."""
from datetime import UTC, datetime
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from backend.app.tables import (
    ApprovalRow,
    CitizenReportRow,
    EvidenceRow,
    NegotiationMessageRow,
    PlanRow,
    RiskWindowRow,
    RunRow,
    ScenarioRow,
    SegmentRow,
    VerificationRow,
    WorkRow,
)
from contracts.models import (
    Approval,
    CitizenReport,
    Evidence,
    NegotiationMessage,
    Plan,
    RiskWindow,
    RunResult,
    Scenario,
    Verification,
    Work,
)

# clock_timestamp(): real server time with microseconds, so rows saved in one transaction still sort
_NOW = func.clock_timestamp


# ---------- city ----------
def put_scenario(s: Session, scenario: Scenario) -> None:
    data = scenario.model_dump(mode="json")
    s.merge(ScenarioRow(seed=scenario.seed, start_date=scenario.start_date, data=data, updated_at=datetime.now(UTC)))
    for seg, d in zip(scenario.segments, data["segments"], strict=True):
        s.merge(SegmentRow(segment_id=seg.segment_id, name=seg.name, road_class=d["road_class"], low_lying=seg.low_lying,
                           protected_until=seg.protected_until, geom=from_shape(LineString(seg.coords), srid=4326), data=d))
    s.execute(delete(WorkRow).where(WorkRow.seed == scenario.seed))
    s.add_all(WorkRow(seed=scenario.seed, work_id=w["work_id"], ord=i, added=False, data=w) for i, w in enumerate(data["works"]))
    s.flush()


def get_scenario(s: Session, seed: int) -> Scenario | None:
    row = s.get(ScenarioRow, seed)
    if row is None:
        return None
    works = s.scalars(select(WorkRow.data).where(WorkRow.seed == seed).order_by(WorkRow.ord)).all()
    return Scenario.model_validate({**row.data, "works": works})


def add_work(s: Session, seed: int, work: Work) -> Work:
    if s.get(WorkRow, (seed, work.work_id)):
        raise ValueError("exists")
    row = s.get(ScenarioRow, seed)
    known = {g["segment_id"] for g in row.data["segments"]} if row else set()
    if not set(work.segment_ids) <= known:
        raise ValueError("unknown segment")
    last = s.scalar(select(func.max(WorkRow.ord)).where(WorkRow.seed == seed))
    s.add(WorkRow(seed=seed, work_id=work.work_id, ord=0 if last is None else last + 1, added=True,
                  data=work.model_dump(mode="json")))
    s.flush()
    return work


def segments_geojson(s: Session, bbox: tuple[float, float, float, float] | None) -> dict[str, Any]:
    q = select(SegmentRow).order_by(SegmentRow.segment_id)
    if bbox:
        q = q.where(func.ST_Intersects(SegmentRow.geom, func.ST_MakeEnvelope(*bbox, 4326)))
    features = [{
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": r.data["coords"]},
        "properties": {"segment_id": r.segment_id, "name": r.name, "road_class": r.road_class, "low_lying": r.low_lying,
                       "protected_until": r.protected_until.isoformat() if r.protected_until else None},
    } for r in s.scalars(q)]
    return {"type": "FeatureCollection", "features": features}


# ---------- plans ----------
def save_plan(s: Session, plan: Plan) -> None:
    d = plan.model_dump(mode="json")
    row = s.get(PlanRow, plan.plan_id)
    if row is None:
        row = PlanRow(plan_id=plan.plan_id, saved_at=_NOW())
        s.add(row)
    row.seed, row.variant, row.status, row.base_plan_id, row.data = plan.seed, d["variant"], d["status"], plan.base_plan_id, d
    if d["status"] == "approved":
        older = select(PlanRow).where(PlanRow.seed == plan.seed, PlanRow.status == "approved", PlanRow.plan_id != plan.plan_id)
        for r in s.scalars(older):
            r.status, r.data = "superseded", {**r.data, "status": "superseded"}
    s.flush()


def get_plan(s: Session, plan_id: str) -> Plan | None:
    row = s.get(PlanRow, plan_id)
    return Plan.model_validate(row.data) if row else None


def _plans(s: Session, seed: int, status: str | None = None) -> list[Plan]:
    q = select(PlanRow.data).where(PlanRow.seed == seed).order_by(PlanRow.saved_at.desc(), PlanRow.plan_id.desc())
    if status:
        q = q.where(PlanRow.status == status)
    return [Plan.model_validate(d) for d in s.scalars(q)]


def list_plans(s: Session, seed: int) -> list[Plan]:
    return _plans(s, seed)


def active_plan(s: Session, seed: int) -> Plan | None:
    """Newest approved plan; else newest waiting for approval; else the old way."""
    for status in ("approved", "waiting_approval"):
        if found := _plans(s, seed, status)[:1]:
            return found[0]
    return get_plan(s, f"P-OLD-{seed}")


# ---------- runs and negotiation ----------
def create_run(s: Session, run_id: str, seed: int, reason: str) -> RunResult:
    result = RunResult(run_id=run_id, status="running")
    s.add(RunRow(run_id=run_id, seed=seed, reason=reason, status=result.status, created_at=_NOW(), updated_at=_NOW(),
                 data=result.model_dump(mode="json")))
    s.flush()
    return result


def update_run(s: Session, result: RunResult) -> None:
    row = s.get(RunRow, result.run_id)
    row.status, row.updated_at, row.data = result.status, _NOW(), result.model_dump(mode="json")
    s.flush()


def get_run(s: Session, run_id: str) -> RunResult | None:
    row = s.get(RunRow, run_id)
    return RunResult.model_validate(row.data) if row else None


def newest_run_id(s: Session, seed: int) -> str | None:
    return s.scalar(select(RunRow.run_id).where(RunRow.seed == seed)
                    .order_by(RunRow.created_at.desc(), RunRow.run_id.desc()).limit(1))


def save_message(s: Session, msg: NegotiationMessage) -> None:
    s.merge(NegotiationMessageRow(run_id=msg.run_id, msg_id=msg.msg_id, round=msg.round, ts=msg.ts,
                                  data=msg.model_dump(mode="json")))
    s.flush()


def list_messages(s: Session, run_id: str) -> list[NegotiationMessage]:
    q = (select(NegotiationMessageRow.data).where(NegotiationMessageRow.run_id == run_id)
         .order_by(NegotiationMessageRow.ts, NegotiationMessageRow.msg_id))
    return [NegotiationMessage.model_validate(d) for d in s.scalars(q)]


# ---------- risk windows ----------
def add_window(s: Session, seed: int, window: RiskWindow) -> None:
    d = window.model_dump(mode="json")
    s.add(RiskWindowRow(window_id=window.window_id, seed=seed, kind=d["kind"], source=window.source, created_at=_NOW(), data=d))
    s.flush()


def list_windows(s: Session, seed: int) -> list[RiskWindow]:
    q = select(RiskWindowRow.data).where(RiskWindowRow.seed == seed).order_by(RiskWindowRow.created_at, RiskWindowRow.window_id)
    return [RiskWindow.model_validate(d) for d in s.scalars(q)]


# ---------- approvals ----------
def _approval_row(row: ApprovalRow, a: Approval) -> None:
    row.plan_id, row.run_id, row.tier, row.status = a.plan_id, a.run_id, a.tier, a.status
    row.requested_at, row.decided_at, row.decided_by, row.reason = a.requested_at, a.decided_at, a.decided_by, a.reason
    row.data = a.model_dump(mode="json")


def add_approval(s: Session, approval: Approval) -> None:
    row = ApprovalRow(approval_id=approval.approval_id)
    _approval_row(row, approval)
    s.add(row)
    s.flush()


def get_approval(s: Session, approval_id: str, lock: bool = False) -> Approval | None:
    """lock: hold the row until the transaction ends, so two people cannot decide the same approval."""
    row = s.get(ApprovalRow, approval_id, with_for_update=lock)
    return Approval.model_validate(row.data) if row else None


def list_approvals(s: Session, status: str | None = None) -> list[Approval]:
    q = select(ApprovalRow.data).order_by(ApprovalRow.requested_at.desc(), ApprovalRow.approval_id.desc())
    if status:
        q = q.where(ApprovalRow.status == status)
    return [Approval.model_validate(d) for d in s.scalars(q)]


def decide_approval(s: Session, approval_id: str, status: str, by: str, reason: str | None) -> Approval:
    row = s.get(ApprovalRow, approval_id)
    if row is None:
        raise ValueError("unknown approval")
    decided = Approval.model_validate(row.data).model_copy(
        update={"status": status, "decided_at": datetime.now(UTC), "decided_by": by, "reason": reason})
    _approval_row(row, decided)
    s.flush()
    return decided


def db_now(s: Session) -> datetime:
    """The database clock, so a row's time and the time in its JSON are the same value."""
    return s.scalar(select(_NOW()))


# ---------- photos ----------
def add_evidence(s: Session, seed: int, ev: Evidence, rel_path: str, place_from: str, time_from: str) -> None:
    s.add(EvidenceRow(evidence_id=ev.evidence_id, seed=seed, work_id=ev.work_id, kind=ev.kind, rel_path=rel_path,
                      phash=ev.phash, lat=ev.lat, lon=ev.lon, taken_at=ev.taken_at, place_from=place_from,
                      time_from=time_from, uploaded_at=ev.uploaded_at, data=ev.model_dump(mode="json")))
    s.flush()


def _evidence(s: Session, *where: Any) -> list[Evidence]:
    q = select(EvidenceRow.data).where(*where).order_by(EvidenceRow.uploaded_at, EvidenceRow.evidence_id)
    return [Evidence.model_validate(d) for d in s.scalars(q)]


def list_evidence(s: Session, seed: int, work_id: str) -> list[Evidence]:
    """A work's photos, oldest first."""
    return _evidence(s, EvidenceRow.seed == seed, EvidenceRow.work_id == work_id)


def evidence_of_others(s: Session, seed: int, work_id: str) -> list[Evidence]:
    """Every photo of the other works in this test case, oldest first."""
    return _evidence(s, EvidenceRow.seed == seed, EvidenceRow.work_id != work_id)


def evidence_path(s: Session, evidence_id: str) -> str | None:
    return s.scalar(select(EvidenceRow.rel_path).where(EvidenceRow.evidence_id == evidence_id))


# ---------- checks and resident answers ----------
def add_verification(s: Session, seed: int, v: Verification) -> None:
    s.add(VerificationRow(verification_id=v.verification_id, seed=seed, work_id=v.work_id, result=v.result,
                          decided_at=v.decided_at, data=v.model_dump(mode="json")))
    s.flush()


def _newest_verifications(seed: int) -> Any:
    return (select(VerificationRow.work_id, VerificationRow.data).where(VerificationRow.seed == seed)
            .ext(distinct_on(VerificationRow.work_id))
            .order_by(VerificationRow.work_id, VerificationRow.decided_at.desc(), VerificationRow.verification_id.desc()))


def latest_verification(s: Session, seed: int, work_id: str) -> Verification | None:
    row = s.execute(_newest_verifications(seed).where(VerificationRow.work_id == work_id)).first()
    return Verification.model_validate(row.data) if row else None


def latest_verifications(s: Session, seed: int) -> dict[str, Verification]:
    """The newest check of every work that has one."""
    return {r.work_id: Verification.model_validate(r.data) for r in s.execute(_newest_verifications(seed))}


def add_report(s: Session, seed: int, report: CitizenReport) -> None:
    s.add(CitizenReportRow(report_id=report.report_id, seed=seed, kind=report.kind, work_id=report.work_id,
                           created_at=report.created_at, data=report.model_dump(mode="json")))
    s.flush()


def confirmations(s: Session, seed: int, work_id: str) -> list[CitizenReport]:
    """A work's resident answers, oldest first."""
    q = (select(CitizenReportRow.data)
         .where(CitizenReportRow.seed == seed, CitizenReportRow.kind == "confirmation", CitizenReportRow.work_id == work_id)
         .order_by(CitizenReportRow.created_at, CitizenReportRow.report_id))
    return [CitizenReport.model_validate(d) for d in s.scalars(q)]
