from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, datetime: DateTime(timezone=True)}


class ScenarioRow(Base):
    __tablename__ = "scenarios"
    seed: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    start_date: Mapped[date]
    data: Mapped[dict[str, Any]]
    updated_at: Mapped[datetime]


class SegmentRow(Base):
    __tablename__ = "segments"
    segment_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    road_class: Mapped[str]
    low_lying: Mapped[bool]
    protected_until: Mapped[date | None]
    geom: Mapped[Any] = mapped_column(Geometry("LINESTRING", srid=4326))
    data: Mapped[dict[str, Any]]


class WorkRow(Base):
    __tablename__ = "works"
    seed: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    work_id: Mapped[str] = mapped_column(primary_key=True)
    ord: Mapped[int]
    added: Mapped[bool]
    data: Mapped[dict[str, Any]]


class PlanRow(Base):
    __tablename__ = "plans"
    plan_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int] = mapped_column(index=True)
    variant: Mapped[str]
    status: Mapped[str]
    saved_at: Mapped[datetime]
    base_plan_id: Mapped[str | None]
    data: Mapped[dict[str, Any]]


class RunRow(Base):
    __tablename__ = "runs"
    run_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int]
    reason: Mapped[str]
    status: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class NegotiationMessageRow(Base):
    __tablename__ = "negotiation_messages"
    run_id: Mapped[str] = mapped_column(primary_key=True)
    msg_id: Mapped[str] = mapped_column(primary_key=True)
    round: Mapped[int]
    ts: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class RiskWindowRow(Base):
    __tablename__ = "risk_windows"
    window_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int]
    kind: Mapped[str]
    source: Mapped[str]
    created_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class ApprovalRow(Base):
    __tablename__ = "approvals"
    approval_id: Mapped[str] = mapped_column(primary_key=True)
    plan_id: Mapped[str]
    run_id: Mapped[str]
    tier: Mapped[str]
    status: Mapped[str]
    requested_at: Mapped[datetime]
    decided_at: Mapped[datetime | None]
    decided_by: Mapped[str | None]
    reason: Mapped[str | None]
    data: Mapped[dict[str, Any]]


class LedgerRow(Base):
    __tablename__ = "ledger"
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    ts: Mapped[datetime]
    actor: Mapped[str]
    action: Mapped[str]
    entity: Mapped[str]
    summary: Mapped[str]
    payload: Mapped[dict[str, Any]]
    prev_hash: Mapped[str]
    hash: Mapped[str]


class EvidenceRow(Base):
    __tablename__ = "evidence"
    evidence_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int] = mapped_column(index=True)
    work_id: Mapped[str] = mapped_column(index=True)
    kind: Mapped[str]
    rel_path: Mapped[str]
    phash: Mapped[str]
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    taken_at: Mapped[datetime | None]
    place_from: Mapped[str]  # "photo", "phone" or "none"
    time_from: Mapped[str]
    uploaded_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class VerificationRow(Base):
    __tablename__ = "verifications"
    verification_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int]
    work_id: Mapped[str] = mapped_column(index=True)
    result: Mapped[str]
    decided_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class CitizenReportRow(Base):
    __tablename__ = "citizen_reports"
    report_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int]
    kind: Mapped[str]
    work_id: Mapped[str | None]
    created_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class AuditorFlagRow(Base):
    __tablename__ = "auditor_flags"
    __table_args__ = (UniqueConstraint("seed", "key"),)
    flag_id: Mapped[str] = mapped_column(primary_key=True)
    seed: Mapped[int] = mapped_column(index=True)
    key: Mapped[str]  # "<rule>:<subject>"
    rule: Mapped[str]
    severity: Mapped[str]
    work_id: Mapped[str | None]
    created_at: Mapped[datetime]
    data: Mapped[dict[str, Any]]


class IdCounterRow(Base):
    __tablename__ = "id_counters"
    prefix: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[int]
