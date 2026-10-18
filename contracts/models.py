"""Frozen data contracts shared by every track. Change only by team agreement (see AGENTS.md)."""
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- city ----------
class Dept(StrEnum):
    water = "water"
    drainage = "drainage"
    gas = "gas"
    power = "power"
    telecom = "telecom"
    roads = "roads"


Sender = Literal["water", "drainage", "gas", "power", "telecom", "roads", "coordinator", "solver"]
Tier = Literal["auto", "department_officer", "ward_engineer", "commissioner"]


class RoadClass(StrEnum):
    trunk = "trunk"
    primary = "primary"
    secondary = "secondary"
    tertiary = "tertiary"
    unclassified = "unclassified"
    residential = "residential"
    service = "service"


class Mode(StrEnum):
    open_cut = "open_cut"
    trenchless = "trenchless"


class Segment(Model):
    segment_id: str  # "S-0001"
    osm_way_id: int
    name: str | None = None
    road_class: RoadClass
    length_m: float
    lanes: int
    traffic_weight: float  # 0.5 service ... 5.0 trunk
    elevation_m: float | None = None
    low_lying: bool = False
    protected_until: date | None = None  # no-dig register; None = not protected
    neighbors: list[str] = []
    coords: list[tuple[float, float]]  # [(lon, lat), ...]


class WorkModeOption(Model):
    mode: Mode
    duration_days: int
    cost_inr: int  # dig + restoration, from contracts.costs
    lanes_closed: int
    dust: float  # 0..1 per working day


class Work(Model):
    work_id: str  # "W-104"
    dept: Dept
    title: str  # "Water main"
    road_name: str  # "Munchur Road"
    segment_ids: list[str]
    length_m: float
    requested_start: int  # day index the department asked for (the old way uses it)
    earliest_start: int
    latest_end: int  # last allowed day index, inclusive
    modes: list[WorkModeOption]  # first = the department's default
    priority: int = 3  # 1 low ... 5 critical
    depends_on: list[str] = []  # works that must finish before this one starts
    deposit_inr: int
    is_emergency: bool = False
    done: bool = False  # finished before the planning window


class ParallelGroup(Model):
    group_id: str  # "G1"
    work_ids: list[str]
    segment_ids: list[str]
    saving_inr: int


class RiskKind(StrEnum):
    rain = "rain"
    air = "air"
    event = "event"


class RiskWindow(Model):
    window_id: str
    kind: RiskKind
    start_day: int
    end_day: int  # inclusive
    segment_ids: list[str]  # rain: low-lying segments; air: every segment; event: its route
    value: float  # rain mm in 24 h, AQI (India) or 0 for events
    source: Literal["open-meteo", "fixture", "override", "event"]
    label: str  # "Heavy rain, 14–15 Nov"


class Scenario(Model):
    seed: int
    city: str = "Surathkal"
    start_date: date  # day index 0
    horizon_days: int = 28
    segments: list[Segment]
    works: list[Work]
    risk_windows: list[RiskWindow] = []
    parallel_groups: list[ParallelGroup] = []


# ---------- plans ----------
class Assignment(Model):
    work_id: str
    start_day: int
    end_day: int  # inclusive
    mode: Mode
    shared_group: str | None = None
    reason: str = ""  # one plain line: "Shares one trench with T-221."


class PlanVariant(StrEnum):
    naive = "naive"  # old way: first come, first dug
    solver_only = "solver_only"  # scheduler without agents or forecasts
    agents = "agents"  # scheduler + negotiation, no forecasts
    orchestrated = "orchestrated"  # everything
    whatif = "whatif"  # a what-if copy, never approved


class PlanStatus(StrEnum):
    draft = "draft"
    waiting_approval = "waiting_approval"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class Plan(Model):
    plan_id: str  # "P-0007"
    seed: int
    variant: PlanVariant
    status: PlanStatus = PlanStatus.draft
    created_at: datetime
    assignments: list[Assignment]
    unplanned: list[str] = []  # work ids that could not be placed
    notes: list[str] = []
    objective: float = 0.0
    solve_ms: int = 0
    base_plan_id: str | None = None


class Metrics(Model):
    plan_id: str
    excavations: int
    digs_per_road: float
    lane_closure_hours: float
    trench_hours_in_rain: float
    clashes: int
    days_late: float
    cost_inr: int
    dust_score: float


class WorkChange(Model):
    work_id: str
    dept: Dept
    title: str  # "Water main, Munchur Road · W-104"
    from_start: int | None
    from_end: int | None
    to_start: int
    to_end: int
    mode_from: Mode | None
    mode_to: Mode
    shared_group: str | None = None
    reason: str
    cost_delta_inr: int


class ConflictKind(StrEnum):
    same_road = "same_road"  # overlapping days on a shared segment, not in one trench
    protected_road = "protected_road"  # open cut on a protected segment
    risk = "risk"  # open cut inside a rain, air or event window
    order = "order"  # resurfacing before a utility dig on the same segment


class Conflict(Model):
    conflict_id: str
    kind: ConflictKind
    work_ids: list[str]
    segment_ids: list[str]
    start_day: int
    end_day: int
    note: str


# ---------- negotiation ----------
class MessageType(StrEnum):
    NOTICE = "NOTICE"
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"
    ESCALATE = "ESCALATE"
    DECISION = "DECISION"


class NegotiationOption(Model):
    label: str  # "A · Shared trench, 10–15 Nov"
    work_id: str
    start_day: int
    mode: Mode
    shared_group: str | None = None
    cost_delta_inr: int  # from contracts.costs, never from the LLM


class NegotiationMessage(Model):
    msg_id: str
    run_id: str
    round: int
    sender: Sender
    recipients: list[str]
    type: MessageType
    work_ids: list[str]
    body: str
    options: list[NegotiationOption] = []
    chosen_option: int | None = None
    ts: datetime


class SolveConstraints(Model):
    pinned_start: dict[str, int] = {}
    min_start: dict[str, int] = {}
    shared_groups: list[str] = []  # accepted parallel groups
    forbidden_days: dict[str, list[int]] = {}
    use_risk: bool = True
    use_groups: bool = True
    time_limit_s: float = 5.0


class NegotiationOutcome(Model):
    run_id: str
    rounds: int
    messages: list[NegotiationMessage]
    constraints: SolveConstraints
    escalated: list[str] = []
    used_llm: bool


# ---------- rules and approvals ----------
class RuleCheck(Model):
    name: str  # "protected_roads", "deposits", "rain", "air", "events", "order"
    severity: Literal["ok", "warn", "fail"]
    detail: str


class PolicyResult(Model):
    plan_id: str
    passed: bool  # False if any check is "fail"
    checks: list[RuleCheck]
    tier: Tier
    works_changed: int
    cost_delta_inr: int


class Approval(Model):
    approval_id: str
    plan_id: str
    run_id: str
    tier: Tier
    status: Literal["pending", "approved", "rejected"]
    summary: str
    requested_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    reason: str | None = None


# ---------- verification ----------
class Evidence(Model):
    evidence_id: str
    work_id: str
    kind: Literal["before", "after", "citizen"]
    file_url: str
    lat: float | None = None
    lon: float | None = None
    taken_at: datetime | None = None
    phash: str
    uploaded_at: datetime


class VerificationCheck(Model):
    name: Literal["place", "time", "reuse", "repair", "resident", "inspection"]
    status: Literal["ok", "fail", "warn", "pending"]
    detail: str


class Verification(Model):
    verification_id: str
    work_id: str
    result: Literal["verified", "held", "inspect", "pending"]
    checks: list[VerificationCheck]
    deposit_inr: int
    deposit_released: bool
    decided_at: datetime


class CitizenReport(Model):
    report_id: str
    kind: Literal["emergency", "confirmation"]
    category: Literal["water", "gas", "power", "cavein", "trench"] | None = None
    work_id: str | None = None
    answer: Literal["yes", "notyet"] | None = None
    problems: list[str] = []
    lat: float | None = None
    lon: float | None = None
    note: str = ""
    photo_url: str | None = None
    created_at: datetime


# ---------- public record ----------
class LedgerEntry(Model):
    seq: int
    ts: datetime
    actor: str  # "scheduler", "ward_engineer", "water", "rules", "photo_check", "resident", "forecast"
    action: str  # "plan.decided", "plan.approved", "evidence.added", ...
    entity: str  # "plan:P-0007", "work:W-104"
    summary: str  # plain words for the public record
    payload: dict[str, Any]
    prev_hash: str
    hash: str


class LedgerVerify(Model):
    ok: bool
    entries: int
    first_bad_seq: int | None = None


class Reason(Model):
    icon: str  # a design-system Icon name
    lead: str
    text: str
    source: str


class Explanation(Model):
    entity: str
    title: str
    reasons: list[Reason]
    rules: list[RuleCheck]
    ledger_seqs: list[int]


class AuditorFlag(Model):
    flag_id: str
    severity: Literal["fail", "warn", "ok"]
    word: str  # badge word: "Photo reused", "Look again", "Reviewed"
    work_id: str | None = None
    text: str
    ledger_seq: int | None = None
    created_at: datetime


# ---------- live updates ----------
class CopilotStep(Model):
    step_id: str
    text: str
    detail: str | None = None
    status: Literal["done", "running", "needs", "waiting"]


class UiAction(Model):
    action: Literal["select_work", "set_day", "open_tab", "fit_work", "toggle_old_way", "open_drawer", "show_toast"]
    args: dict[str, Any] = {}


EventType = Literal[
    "negotiation.message", "plan.updated", "risk.windows_changed", "approval.requested",
    "approval.decided", "verification.result", "ledger.appended", "copilot.step", "ui.action", "auditor.flag",
]


class WsEvent(Model):
    type: EventType
    data: dict[str, Any]
    ts: datetime


# ---------- views and evals ----------
class WorkStatus(StrEnum):
    planned = "planned"
    moved = "moved"
    shared = "shared"
    digging = "digging"
    done = "done"
    verified = "verified"
    held = "held"
    emergency = "emergency"


class WorkView(Model):
    work: Work
    assignment: Assignment | None = None
    status: WorkStatus


class Stat(Model):
    median: float
    low: float
    high: float


class EvalRow(Model):
    variant: Literal["naive", "solver_only", "agents", "risk", "full"]
    digs_per_road: Stat
    lane_closure_hours: Stat
    trench_hours_in_rain: Stat
    clashes: Stat
    days_late: Stat
    cost_inr: Stat


class EvalSummary(Model):
    seeds: list[int]
    rows: list[EvalRow]
    fake_repairs_caught: int
    fake_repairs_total: int
    generated_at: datetime


# ---------- workflow and copilot results ----------
class RunResult(Model):
    run_id: str
    status: Literal["running", "waiting_approval", "approved", "rejected", "failed"]
    plan_id: str | None = None
    approval_id: str | None = None
    metrics: Metrics | None = None
    note: str = ""


class CopilotReply(Model):
    reply_id: str
    text: str
    steps: list[CopilotStep] = []
    actions: list[UiAction] = []
    used_llm: bool
