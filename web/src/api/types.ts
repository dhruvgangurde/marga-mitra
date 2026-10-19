// Mirrors contracts/models.py. Same names, same snake_case fields.

// ---------- city ----------
export type Dept = 'water' | 'drainage' | 'gas' | 'power' | 'telecom' | 'roads';
export type Sender = Dept | 'coordinator' | 'solver';
export type Tier = 'auto' | 'department_officer' | 'ward_engineer' | 'commissioner';
export type RoadClass = 'trunk' | 'primary' | 'secondary' | 'tertiary' | 'unclassified' | 'residential' | 'service';
export type Mode = 'open_cut' | 'trenchless';

export interface Segment {
  segment_id: string;
  osm_way_id: number;
  name?: string | null;
  road_class: RoadClass;
  length_m: number;
  lanes: number;
  traffic_weight: number;
  elevation_m?: number | null;
  low_lying: boolean;
  protected_until?: string | null;
  neighbors: string[];
  coords: [number, number][];
}

export interface WorkModeOption {
  mode: Mode;
  duration_days: number;
  cost_inr: number;
  lanes_closed: number;
  dust: number;
}

export interface Work {
  work_id: string;
  dept: Dept;
  title: string;
  road_name: string;
  segment_ids: string[];
  length_m: number;
  requested_start: number;
  earliest_start: number;
  latest_end: number;
  modes: WorkModeOption[];
  priority: number;
  depends_on: string[];
  deposit_inr: number;
  is_emergency: boolean;
  done: boolean;
}

export interface ParallelGroup {
  group_id: string;
  work_ids: string[];
  segment_ids: string[];
  saving_inr: number;
}

export type RiskKind = 'rain' | 'air' | 'event';

export interface RiskWindow {
  window_id: string;
  kind: RiskKind;
  start_day: number;
  end_day: number;
  segment_ids: string[];
  value: number;
  source: 'open-meteo' | 'fixture' | 'override' | 'event';
  label: string;
}

export interface Scenario {
  seed: number;
  city: string;
  start_date: string;
  horizon_days: number;
  segments: Segment[];
  works: Work[];
  risk_windows: RiskWindow[];
  parallel_groups: ParallelGroup[];
}

// ---------- plans ----------
export interface Assignment {
  work_id: string;
  start_day: number;
  end_day: number;
  mode: Mode;
  shared_group?: string | null;
  reason: string;
}

export type PlanVariant = 'naive' | 'solver_only' | 'agents' | 'orchestrated' | 'whatif';
export type PlanStatus = 'draft' | 'waiting_approval' | 'approved' | 'rejected' | 'superseded';

export interface Plan {
  plan_id: string;
  seed: number;
  variant: PlanVariant;
  status: PlanStatus;
  created_at: string;
  assignments: Assignment[];
  unplanned: string[];
  notes: string[];
  objective: number;
  solve_ms: number;
  base_plan_id?: string | null;
}

export interface Metrics {
  plan_id: string;
  excavations: number;
  digs_per_road: number;
  lane_closure_hours: number;
  trench_hours_in_rain: number;
  clashes: number;
  days_late: number;
  cost_inr: number;
  dust_score: number;
}

export interface WorkChange {
  work_id: string;
  dept: Dept;
  title: string;
  from_start: number | null;
  from_end: number | null;
  to_start: number;
  to_end: number;
  mode_from: Mode | null;
  mode_to: Mode;
  shared_group?: string | null;
  reason: string;
  cost_delta_inr: number;
}

export type ConflictKind = 'same_road' | 'protected_road' | 'risk' | 'order';

export interface Conflict {
  conflict_id: string;
  kind: ConflictKind;
  work_ids: string[];
  segment_ids: string[];
  start_day: number;
  end_day: number;
  note: string;
}

// ---------- negotiation ----------
export type MessageType = 'NOTICE' | 'ACCEPT' | 'COUNTER' | 'ESCALATE' | 'DECISION';

export interface NegotiationOption {
  label: string;
  work_id: string;
  start_day: number;
  mode: Mode;
  shared_group?: string | null;
  cost_delta_inr: number;
}

export interface NegotiationMessage {
  msg_id: string;
  run_id: string;
  round: number;
  sender: Sender;
  recipients: string[];
  type: MessageType;
  work_ids: string[];
  body: string;
  options: NegotiationOption[];
  chosen_option?: number | null;
  ts: string;
}

export interface SolveConstraints {
  pinned_start: Record<string, number>;
  min_start: Record<string, number>;
  shared_groups: string[];
  forbidden_days: Record<string, number[]>;
  use_risk: boolean;
  use_groups: boolean;
  time_limit_s: number;
}

export interface NegotiationOutcome {
  run_id: string;
  rounds: number;
  messages: NegotiationMessage[];
  constraints: SolveConstraints;
  escalated: string[];
  used_llm: boolean;
}

// ---------- rules and approvals ----------
export interface RuleCheck {
  name: string;
  severity: 'ok' | 'warn' | 'fail';
  detail: string;
}

export interface PolicyResult {
  plan_id: string;
  passed: boolean;
  checks: RuleCheck[];
  tier: Tier;
  works_changed: number;
  cost_delta_inr: number;
}

export interface Approval {
  approval_id: string;
  plan_id: string;
  run_id: string;
  tier: Tier;
  status: 'pending' | 'approved' | 'rejected';
  summary: string;
  requested_at: string;
  decided_at?: string | null;
  decided_by?: string | null;
  reason?: string | null;
}

// ---------- verification ----------
export interface Evidence {
  evidence_id: string;
  work_id: string;
  kind: 'before' | 'after' | 'citizen';
  file_url: string;
  lat?: number | null;
  lon?: number | null;
  taken_at?: string | null;
  phash: string;
  uploaded_at: string;
}

export type CheckName = 'place' | 'time' | 'reuse' | 'repair' | 'resident' | 'inspection';
export type CheckStatus = 'ok' | 'fail' | 'warn' | 'pending';

export interface VerificationCheck {
  name: CheckName;
  status: CheckStatus;
  detail: string;
}

export interface Verification {
  verification_id: string;
  work_id: string;
  result: 'verified' | 'held' | 'inspect' | 'pending';
  checks: VerificationCheck[];
  deposit_inr: number;
  deposit_released: boolean;
  decided_at: string;
}

export interface CitizenReport {
  report_id: string;
  kind: 'emergency' | 'confirmation';
  category?: 'water' | 'gas' | 'power' | 'cavein' | 'trench' | null;
  work_id?: string | null;
  answer?: 'yes' | 'notyet' | null;
  problems: string[];
  lat?: number | null;
  lon?: number | null;
  note: string;
  photo_url?: string | null;
  created_at: string;
}

// ---------- public record ----------
export interface LedgerEntry {
  seq: number;
  ts: string;
  actor: string;
  action: string;
  entity: string;
  summary: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface LedgerVerify {
  ok: boolean;
  entries: number;
  first_bad_seq?: number | null;
}

export interface Reason {
  icon: string;
  lead: string;
  text: string;
  source: string;
}

export interface Explanation {
  entity: string;
  title: string;
  reasons: Reason[];
  rules: RuleCheck[];
  ledger_seqs: number[];
}

export interface AuditorFlag {
  flag_id: string;
  severity: 'fail' | 'warn' | 'ok';
  word: string;
  work_id?: string | null;
  text: string;
  ledger_seq?: number | null;
  created_at: string;
}

// ---------- live updates ----------
export interface CopilotStep {
  step_id: string;
  text: string;
  detail?: string | null;
  status: 'done' | 'running' | 'needs' | 'waiting';
}

export type UiActionName =
  | 'select_work' | 'set_day' | 'open_tab' | 'fit_work' | 'toggle_old_way' | 'open_drawer' | 'show_toast';

export interface UiAction {
  action: UiActionName;
  args: Record<string, unknown>;
}

export type EventType =
  | 'negotiation.message' | 'plan.updated' | 'risk.windows_changed' | 'approval.requested'
  | 'approval.decided' | 'verification.result' | 'ledger.appended' | 'copilot.step' | 'ui.action' | 'auditor.flag';

export interface WsEvent {
  type: EventType;
  data: Record<string, unknown>;
  ts: string;
}

// ---------- views and evals ----------
export type WorkStatus = 'planned' | 'moved' | 'shared' | 'digging' | 'done' | 'verified' | 'held' | 'emergency';

export interface WorkView {
  work: Work;
  assignment?: Assignment | null;
  status: WorkStatus;
}

export interface Stat {
  median: number;
  low: number;
  high: number;
}

export interface EvalRow {
  variant: 'naive' | 'solver_only' | 'agents' | 'risk' | 'full';
  digs_per_road: Stat;
  lane_closure_hours: Stat;
  trench_hours_in_rain: Stat;
  clashes: Stat;
  days_late: Stat;
  cost_inr: Stat;
}

export interface EvalSummary {
  seeds: number[];
  rows: EvalRow[];
  fake_repairs_caught: number;
  fake_repairs_total: number;
  generated_at: string;
}

// ---------- workflow and copilot results ----------
export interface RunResult {
  run_id: string;
  status: 'running' | 'waiting_approval' | 'approved' | 'rejected' | 'failed';
  plan_id?: string | null;
  approval_id?: string | null;
  metrics?: Metrics | null;
  note: string;
}

export interface CopilotReply {
  reply_id: string;
  text: string;
  steps: CopilotStep[];
  actions: UiAction[];
  used_llm: boolean;
}

// ---------- web-only shapes (endpoint replies that have no model) ----------
export interface Health {
  ok: boolean;
  db: boolean;
  llm_provider: string;
  weather_mode: string;
}

export interface ScenarioLoad {
  seed: number;
  start_date: string;
  works: number;
  segments: number;
}

export interface Department {
  id: Dept;
  name: string;
  icon: string;
  color_token: string;
}

export interface NoDigEntry {
  segment_id: string;
  name: string;
  protected_until: string;
  why: string;
}

export interface WhatIfResult {
  plan: Plan;
  diff: WorkChange[];
  metrics: Metrics;
}

export interface SegmentFeature {
  type: 'Feature';
  geometry: { type: 'LineString'; coordinates: [number, number][] };
  properties: {
    segment_id: string;
    name: string | null;
    road_class: RoadClass;
    low_lying: boolean;
    protected_until: string | null;
  };
}

export interface SegmentCollection {
  type: 'FeatureCollection';
  features: SegmentFeature[];
}

// ---------- request bodies (the same for the mock server and the real API) ----------
export interface ForecastOverrideBody {
  kind: RiskKind;
  start_day: number;
  end_day: number;
  value: number;
  label?: string;
}

export interface EventBody {
  label: string;
  start_day: number;
  end_day: number;
  segment_ids: string[];
}

export interface DecideBody {
  decision: 'approve' | 'reject';
  by: string;
  reason?: string;
}

export interface EvidenceInput {
  kind: 'before' | 'after' | 'citizen';
  photo: Blob;
  lat?: number;
  lon?: number;
  takenAt?: string;
}

export interface ConfirmBody {
  work_id: string;
  answer: 'yes' | 'notyet';
  problems: string[];
  lat?: number;
  lon?: number;
}

export interface EmergencyInput {
  category: 'water' | 'gas' | 'power' | 'cavein' | 'trench';
  lat: number;
  lon: number;
  note?: string;
  photo?: Blob;
}

export interface WhatIfBody {
  work_id: string;
  delay_days: number;
}

export interface CopilotBody {
  message: string;
  context?: Record<string, unknown>;
}

export interface LedgerOpts {
  limit?: number;
  beforeSeq?: number;
}