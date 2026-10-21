// In-memory stand-in for the backend, built from data.ts. It never uses the network.
// Every function waits 250 ms and returns a deep copy, like a real request would.
import { ApiError } from '../api/client';
import { dayRange, inr, TODAY_DAY } from '../api/format';
import type {
  Approval, Assignment, AuditorFlag, CitizenReport, ConfirmBody, CopilotBody, CopilotReply, CopilotStep, DecideBody, Department,
  EmergencyInput, EvalSummary, EventBody, EventType, Evidence, EvidenceInput, Explanation, ForecastOverrideBody,
  Health, LedgerEntry, LedgerOpts, LedgerVerify, Metrics, NegotiationMessage, NoDigEntry, Plan, RiskWindow,
  RunResult, ScenarioLoad, Segment, SegmentCollection, UiAction, Verification, WhatIfBody, WhatIfResult, Work, WorkChange,
  WorkStatus, WorkView,
} from '../api/types';
import { mockBus } from './bus';
import {
  APPROVAL_HISTORY, APPROVALS, AUDITOR_FLAGS, DEPARTMENTS, DIFFS, EVAL_SUMMARY, EVENT_ROADS, EVIDENCE, explainWork,
  inspectChecks, LEDGER, MESSAGES_RUN_0007, MESSAGES_RUN_0008, METRICS, NO_DIG, OV_1, OV_1_WORK_IDS, PHOTOS, PLANS,
  RAIN_TRENCH_HOURS, RISK_WINDOWS, SCENARIO, VERIFICATIONS, verifiedChecks, WORKS,
} from './data';

const DELAY_MS = 250;
const RUN_7_GAP_MS = 900;
const RUN_8_GAP_MS = 700;
const NEGOTIATING_FINISH_MS = 1500;

interface State {
  works: Work[];
  plans: Plan[];
  metrics: Metrics[];
  runs: RunResult[];
  messages: NegotiationMessage[];
  approvals: Approval[];
  ledger: LedgerEntry[];
  risk: RiskWindow[];
  evidence: Evidence[];
  verifications: Verification[];
  reports: CitizenReport[];
  nextEvidence: number;
  nextVerification: number;
  nextEvent: number;
  timers: ReturnType<typeof setTimeout>[];
}

const copy = <T>(value: T): T => structuredClone(value);
const wait = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));
const pad = (n: number): string => String(n).padStart(4, '0');

// The demo clock starts just after the last entry of the public record and then runs in real time.
const BOOT_MS = Date.now();
const DEMO_START_MS = Date.parse('2026-11-10T10:07:00+05:30');

function demoNow(): string {
  const ms = DEMO_START_MS + (Date.now() - BOOT_MS) + 5.5 * 3600 * 1000;
  return new Date(ms).toISOString().slice(0, 19) + '+05:30';
}

function hashFor(seq: number, text: string): string {
  let out = '';
  for (let i = 0; i < 8; i += 1) {
    let h = 2166136261 ^ (seq * 31 + i);
    const s = `${seq}:${i}:${text}`;
    for (let c = 0; c < s.length; c += 1) h = Math.imul(h ^ s.charCodeAt(c), 16777619);
    out += (h >>> 0).toString(16).padStart(8, '0');
  }
  return out;
}

// ---------- state ----------
function segmentsOfWorks(works: Work[], ids: string[]): string[] {
  const out = new Set<string>();
  works.filter((w) => ids.includes(w.work_id)).forEach((w) => w.segment_ids.forEach((s) => out.add(s)));
  return [...out];
}

function eventWindow(works: Work[]): RiskWindow {
  const base = RISK_WINDOWS.find((w) => w.window_id === 'EV-DEMO') as RiskWindow;
  const onRoads = works.filter((w) => EVENT_ROADS.includes(w.road_name)).map((w) => w.work_id);
  return { ...copy(base), segment_ids: segmentsOfWorks(works, onRoads) };
}

function rainWindow(works: Work[]): RiskWindow {
  return { ...copy(OV_1), segment_ids: segmentsOfWorks(works, OV_1_WORK_IDS) };
}

function addRun7(st: State, messageCount: number, finished: boolean): void {
  st.messages.push(...copy(MESSAGES_RUN_0007.slice(0, messageCount)));
  st.runs.push({
    run_id: 'RUN-0007',
    status: finished ? 'waiting_approval' : 'running',
    plan_id: finished ? 'P-0007' : null,
    approval_id: finished ? 'A-0001' : null,
    metrics: finished ? copy(METRICS[1]) : null,
    note: '',
  });
  if (finished) {
    st.plans.push(copy(PLANS[1]));
    st.metrics.push(copy(METRICS[1]));
    st.approvals.push(copy(APPROVALS[0]));
  }
}

function addRain(st: State): void {
  st.risk.push(rainWindow(st.works));
  (st.plans.find((p) => p.plan_id === 'P-0007') as Plan).status = 'superseded';
  st.plans.push(copy(PLANS[2]));
  st.metrics.push(copy(METRICS[2]));
  st.messages.push(...copy(MESSAGES_RUN_0008));
  st.approvals.push(copy(APPROVALS[1]));
  st.runs.push({
    run_id: 'RUN-0008', status: 'waiting_approval', plan_id: 'P-0008', approval_id: 'A-0002',
    metrics: copy(METRICS[2]), note: '',
  });
  setRainHours(st);
}

function setRainHours(st: State): void {
  st.metrics.filter((m) => m.plan_id === 'P-OLD-1' || m.plan_id === 'P-0007').forEach((m) => {
    m.trench_hours_in_rain = RAIN_TRENCH_HOURS;
  });
}

function freshState(name: string): State {
  const works = copy(WORKS).map((w) => {
    const fromScenario = SCENARIO.works.find((s) => s.work_id === w.work_id);
    return { ...w, segment_ids: fromScenario ? [...fromScenario.segment_ids] : [] };
  });
  const st: State = {
    works,
    plans: [copy(PLANS[0])],
    metrics: [copy(METRICS[0])],
    runs: [],
    messages: [],
    approvals: copy(APPROVAL_HISTORY),
    ledger: copy(LEDGER),
    risk: copy(RISK_WINDOWS),
    evidence: copy(EVIDENCE),
    verifications: copy(VERIFICATIONS),
    reports: [],
    nextEvidence: 6, // E-0004 and E-0005 are the screenshot photos
    nextVerification: 2,
    nextEvent: 1,
    timers: [],
  };
  st.risk[0] = eventWindow(works);
  if (name === 'old') return st;
  if (name === 'negotiating') {
    addRun7(st, 5, false);
    return st;
  }
  addRun7(st, 6, true);
  if (name === 'approved') {
    const plan = st.plans.find((p) => p.plan_id === 'P-0007') as Plan;
    const approval = st.approvals.find((a) => a.approval_id === 'A-0001') as Approval;
    plan.status = 'approved';
    approval.status = 'approved';
    approval.decided_at = '2026-11-10T10:06:40+05:30';
    approval.decided_by = 'ward_engineer';
    (st.runs.find((r) => r.run_id === 'RUN-0007') as RunResult).status = 'approved';
  }
  if (name === 'rain') addRain(st);
  return st;
}

let state: State = freshState('ready');

function later(fn: () => void, ms: number): void {
  state.timers.push(setTimeout(fn, ms));
}

export function applyDemoState(name: string): void {
  state.timers.forEach((t) => clearTimeout(t));
  state = freshState(name);
  if (name === 'negotiating') {
    later(() => {
      deliver(MESSAGES_RUN_0007[5]);
      finishRun7();
    }, NEGOTIATING_FINISH_MS);
  }
}

export function reset(): void {
  applyDemoState('ready');
}

async function reply<T>(read: () => T): Promise<T> {
  await wait(DELAY_MS);
  return copy(read());
}

// ---------- events and the public record ----------
function emit(type: EventType, data: object): void {
  mockBus.emit({ type, data: copy(data) as Record<string, unknown>, ts: demoNow() });
}

function record(actor: string, action: string, entity: string, summary: string): void {
  const last = state.ledger[state.ledger.length - 1];
  const seq = last.seq + 1;
  const entry: LedgerEntry = {
    seq, ts: demoNow(), actor, action, entity, summary, payload: {}, prev_hash: last.hash, hash: hashFor(seq, summary),
  };
  state.ledger.push(entry);
  emit('ledger.appended', entry);
}

function metricsFor(planId: string): Metrics | undefined {
  return state.metrics.find((m) => m.plan_id === planId);
}

function emitPlan(plan: Plan): void {
  emit('plan.updated', {
    plan_id: plan.plan_id, status: plan.status, variant: plan.variant, metrics: metricsFor(plan.plan_id) ?? null,
  });
}

// ---------- lookups ----------
const newest = (plans: Plan[]): Plan | undefined =>
  [...plans].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

const oldPlan = (): Plan => state.plans.find((p) => p.variant === 'naive') as Plan;

function shownPlan(): Plan {
  const waiting = newest(state.plans.filter((p) => p.status === 'waiting_approval'));
  if (waiting) return waiting;
  const approved = newest(state.plans.filter((p) => p.status === 'approved' && p.variant !== 'naive'));
  return approved ?? oldPlan();
}

function requirePlan(planId: string): Plan {
  const plan = state.plans.find((p) => p.plan_id === planId);
  if (!plan) throw new ApiError(404, `Unknown plan ${planId}`);
  return plan;
}

function requireWork(workId: string): Work {
  const work = state.works.find((w) => w.work_id === workId);
  if (!work) throw new ApiError(404, `Unknown work ${workId}`);
  return work;
}

function statusOf(work: Work, assignment: Assignment | null): WorkStatus {
  const verification = state.verifications.find((v) => v.work_id === work.work_id);
  if (work.is_emergency) return 'emergency';
  if (verification?.result === 'verified') return 'verified';
  if (verification?.result === 'held') return 'held';
  if (work.done) return 'done';
  if (assignment?.shared_group) return 'shared';
  if (assignment && TODAY_DAY >= assignment.start_day && TODAY_DAY <= assignment.end_day) return 'digging';
  if (assignment && (assignment.start_day !== work.requested_start || assignment.mode !== work.modes[0].mode)) return 'moved';
  return 'planned';
}

function viewsFor(plan: Plan): WorkView[] {
  return state.works.flatMap((work) => {
    const assignment = plan.assignments.find((a) => a.work_id === work.work_id) ?? null;
    if (!assignment && work.is_emergency) return [];
    return [{ work, assignment, status: statusOf(work, assignment) }];
  });
}

function costOf(work: Work, mode: Assignment['mode']): number {
  return (work.modes.find((m) => m.mode === mode) ?? work.modes[0]).cost_inr;
}

function diffPlans(plan: Plan, base: Plan): WorkChange[] {
  const known = new Map(DIFFS['P-0008'].map((c) => [c.work_id, c.cost_delta_inr]));
  const changes: WorkChange[] = [];
  for (const a of plan.assignments) {
    const work = state.works.find((w) => w.work_id === a.work_id);
    const old = base.assignments.find((x) => x.work_id === a.work_id);
    if (!work) continue;
    const same = old && old.start_day === a.start_day && old.end_day === a.end_day && old.mode === a.mode
      && (old.shared_group ?? null) === (a.shared_group ?? null);
    if (same) continue;
    changes.push({
      work_id: work.work_id,
      dept: work.dept,
      title: `${work.title}, ${work.road_name} · ${work.work_id}`,
      from_start: old?.start_day ?? null,
      from_end: old?.end_day ?? null,
      to_start: a.start_day,
      to_end: a.end_day,
      mode_from: old?.mode ?? null,
      mode_to: a.mode,
      shared_group: a.shared_group ?? null,
      reason: a.reason,
      cost_delta_inr: known.get(work.work_id) ?? (old ? costOf(work, a.mode) - costOf(work, old.mode) : 0),
    });
  }
  return changes;
}

// ---------- runs ----------
function deliver(message: NegotiationMessage): void {
  state.messages.push(copy(message));
  emit('negotiation.message', message);
}

function setRun(runId: string, patch: Partial<RunResult>): RunResult {
  const run = state.runs.find((r) => r.run_id === runId) as RunResult;
  Object.assign(run, patch);
  return run;
}

function openApproval(source: Approval): Approval {
  const existing = state.approvals.find((a) => a.approval_id === source.approval_id);
  if (!existing) {
    const created = copy(source);
    state.approvals.push(created);
    return created;
  }
  Object.assign(existing, { status: 'pending', decided_at: null, decided_by: null, reason: null });
  return existing;
}

function ensurePlan(source: Plan): Plan {
  let plan = state.plans.find((p) => p.plan_id === source.plan_id);
  if (!plan) {
    plan = copy(source);
    state.plans.push(plan);
    state.metrics.push(copy(metricsOf(source.plan_id)));
  }
  return plan;
}

function metricsOf(planId: string): Metrics {
  return METRICS.find((m) => m.plan_id === planId) as Metrics;
}

function finishRun7(): void {
  const plan = ensurePlan(PLANS[1]);
  plan.status = 'waiting_approval';
  const approval = openApproval(APPROVALS[0]);
  setRun('RUN-0007', { status: 'waiting_approval', plan_id: 'P-0007', approval_id: 'A-0001', metrics: copy(metricsOf('P-0007')) });
  emitPlan(plan);
  emit('approval.requested', approval);
  record('scheduler', 'plan.decided', 'plan:P-0007', 'Made a new plan for 2–29 Nov');
}

function finishRun8(): void {
  const p7 = ensurePlan(PLANS[1]);
  const p8 = ensurePlan(PLANS[2]);
  p7.status = 'superseded';
  p8.status = 'waiting_approval';
  const approval = openApproval(APPROVALS[1]);
  setRun('RUN-0008', { status: 'waiting_approval', plan_id: 'P-0008', approval_id: 'A-0002', metrics: copy(metricsOf('P-0008')) });
  emitPlan(p7);
  emitPlan(p8);
  emit('approval.requested', approval);
  record('scheduler', 'plan.decided', 'work:D-412', 'Re-planned after the rain forecast: 3 works moved');
}

function startRun(runId: string, messages: NegotiationMessage[], gap: number, finish: () => void): RunResult {
  state.messages = state.messages.filter((m) => m.run_id !== runId);
  const run: RunResult = { run_id: runId, status: 'running', plan_id: null, approval_id: null, metrics: null, note: '' };
  const index = state.runs.findIndex((r) => r.run_id === runId);
  if (index >= 0) state.runs[index] = run;
  else state.runs.push(run);
  messages.forEach((m, i) => later(() => deliver(m), (i + 1) * gap));
  later(finish, (messages.length + 1) * gap);
  return run;
}

// ---------- flows ----------
export function orchestrate(): Promise<RunResult> {
  return reply(() => {
    const last = state.runs[state.runs.length - 1];
    if (last?.run_id === 'RUN-0008' && last.status === 'rejected') {
      return startRun('RUN-0008', MESSAGES_RUN_0008, RUN_8_GAP_MS, finishRun8);
    }
    if (!last || last.status === 'rejected') {
      return startRun('RUN-0007', MESSAGES_RUN_0007, RUN_7_GAP_MS, finishRun7);
    }
    return last;
  });
}

export function forecastOverride(body: ForecastOverrideBody): Promise<RunResult> {
  return reply(() => {
    const prefix = body.kind === 'rain' ? 'Heavy rain' : body.kind === 'air' ? 'Poor air' : 'Event';
    const days = dayRange(body.start_day, body.end_day);
    state.risk = state.risk.filter((w) => w.window_id !== 'OV-1');
    state.risk.push({
      ...rainWindow(state.works), kind: body.kind, start_day: body.start_day, end_day: body.end_day,
      value: body.value, label: body.label ?? `${prefix}, ${days}`,
    });
    setRainHours(state);
    emit('risk.windows_changed', { windows: state.risk });
    record('forecast', 'forecast.changed', 'plan:P-0008', `${prefix} ${days} (simulated for the demo)`);
    return startRun('RUN-0008', MESSAGES_RUN_0008, RUN_8_GAP_MS, finishRun8);
  });
}

export function decideApproval(approvalId: string, body: DecideBody): Promise<RunResult> {
  return reply(() => {
    const approval = state.approvals.find((a) => a.approval_id === approvalId);
    if (!approval) throw new ApiError(404, `Unknown approval ${approvalId}`);
    if (approval.status !== 'pending') throw new ApiError(409, 'This approval is already decided');
    const reason = body.reason?.trim();
    if (body.decision === 'reject' && !reason) throw new ApiError(422, 'Give a reason to reject');
    const status = body.decision === 'approve' ? 'approved' : 'rejected';
    Object.assign(approval, { status, decided_at: demoNow(), decided_by: body.by, reason: reason ?? null });
    const plan = state.plans.find((p) => p.plan_id === approval.plan_id);
    if (plan) plan.status = status;
    const run = state.runs.find((r) => r.run_id === approval.run_id);
    if (run) run.status = status;
    emit('approval.decided', approval);
    if (plan) emitPlan(plan);
    record(
      body.by, `plan.${status}`, `plan:${approval.plan_id}`,
      status === 'approved' ? 'Approved the plan for 2–29 Nov' : `Rejected the plan: ${reason}`,
    );
    return run ?? { run_id: approval.run_id, status, plan_id: approval.plan_id, approval_id: approvalId, metrics: null, note: '' };
  });
}

export function uploadEvidence(workId: string, input: EvidenceInput): Promise<Evidence> {
  return reply(() => {
    requireWork(workId);
    const now = demoNow();
    const evidence: Evidence = {
      evidence_id: `E-${pad(state.nextEvidence)}`,
      work_id: workId,
      kind: input.kind,
      file_url: URL.createObjectURL(input.photo),
      lat: input.lat ?? null,
      lon: input.lon ?? null,
      taken_at: input.takenAt ?? now,
      phash: hashFor(state.nextEvidence, workId).slice(0, 16),
      uploaded_at: now,
    };
    state.nextEvidence += 1;
    state.evidence.push(evidence);
    record('photo_check', 'evidence.added', `work:${workId}`, `Added a ${input.kind} photo for ${workId}`);
    return evidence;
  });
}

export function verifyWork(workId: string): Promise<Verification> {
  return reply(() => {
    const work = requireWork(workId);
    let verification = state.verifications.find((v) => v.work_id === workId && v.verification_id === 'V-0001');
    if (workId === 'T-230' && verification) {
      emit('verification.result', verification);
      return verification;
    }
    const verified = workId === 'W-104';
    verification = {
      verification_id: `V-${pad(state.nextVerification)}`,
      work_id: workId,
      result: verified ? 'verified' : 'inspect',
      checks: verified ? verifiedChecks() : inspectChecks(),
      deposit_inr: work.deposit_inr,
      deposit_released: verified,
      decided_at: demoNow(),
    };
    state.nextVerification += 1;
    state.verifications = state.verifications.filter((v) => v.work_id !== workId);
    state.verifications.push(verification);
    emit('verification.result', verification);
    record(
      'photo_check', verified ? 'verification.verified' : 'verification.inspect', `work:${workId}`,
      verified ? `Repair verified: ${inr(work.deposit_inr)} released` : `A person must look at the repair of ${workId}`,
    );
    return verification;
  });
}

export function confirmRoad(body: ConfirmBody): Promise<CitizenReport> {
  return reply(() => {
    requireWork(body.work_id);
    const report: CitizenReport = {
      report_id: `CR-${String(state.reports.length + 1).padStart(4, '0')}`,
      kind: 'confirmation',
      work_id: body.work_id,
      answer: body.answer,
      problems: body.problems,
      lat: body.lat ?? null,
      lon: body.lon ?? null,
      note: '',
      created_at: demoNow(),
    };
    state.reports.push(report);
    record(
      'resident', 'report.confirmed', `work:${body.work_id}`,
      body.answer === 'yes' ? 'Resident confirmed the road is restored' : 'Resident says the road is not restored yet',
    );
    return report;
  });
}

export function reportEmergency(input: EmergencyInput): Promise<CitizenReport> {
  return reply(() => {
    // The demo has one emergency story, whatever the category.
    if (!state.works.some((w) => w.work_id === 'W-131')) {
      state.works.push({
        work_id: 'W-131', dept: 'water', title: 'Burst water pipe', road_name: 'Idya Road', segment_ids: [], length_m: 60,
        requested_start: 8, earliest_start: 8, latest_end: 27,
        modes: [{ mode: 'open_cut', duration_days: 2, cost_inr: 292800, lanes_closed: 1, dust: 0.6 }],
        priority: 5, depends_on: [], deposit_inr: 30000, is_emergency: true, done: false,
      });
      const plan = shownPlan();
      plan.assignments.push({
        work_id: 'W-131', start_day: 8, end_day: 9, mode: 'open_cut', shared_group: null,
        reason: 'Emergency dig allowed at once by the rules.',
      });
      emitPlan(plan);
    }
    const report: CitizenReport = {
      report_id: `CR-${String(state.reports.length + 1).padStart(4, '0')}`,
      kind: 'emergency',
      category: input.category,
      work_id: 'W-131',
      problems: [],
      lat: input.lat,
      lon: input.lon,
      note: input.note ?? '',
      photo_url: input.photo ? URL.createObjectURL(input.photo) : null,
      created_at: demoNow(),
    };
    state.reports.push(report);
    record('resident', 'report.added', 'work:W-131', 'Reported a burst water pipe on Idya Road');
    record('rules', 'rules.passed', 'work:W-131', 'Emergency dig allowed at once: burst water pipe');
    return report;
  });
}

export function whatIf(body: WhatIfBody): Promise<WhatIfResult> {
  return reply(() => {
    const base = shownPlan();
    const target = base.assignments.find((a) => a.work_id === body.work_id);
    if (!target) throw new ApiError(404, `Unknown work ${body.work_id}`);
    const moved = new Set([body.work_id]);
    if (target.shared_group) {
      base.assignments.filter((a) => a.shared_group === target.shared_group).forEach((a) => moved.add(a.work_id));
    }
    const plan: Plan = {
      ...copy(base),
      plan_id: 'P-WHATIF',
      variant: 'whatif',
      status: 'draft',
      created_at: demoNow(),
      base_plan_id: base.plan_id,
      assignments: base.assignments.map((a) => (
        moved.has(a.work_id) ? { ...a, start_day: a.start_day + body.delay_days, end_day: a.end_day + body.delay_days } : copy(a)
      )),
    };
    const days = Math.abs(body.delay_days) === 1 ? 'day' : 'days';
    const diff = diffPlans(plan, base).map((c) => ({
      ...c, reason: `Moved by ${body.delay_days} ${days}.`, cost_delta_inr: 2000 * body.delay_days,
    }));
    const shown = metricsFor(base.plan_id) as Metrics;
    const metrics: Metrics = {
      ...copy(shown), plan_id: 'P-WHATIF', days_late: Math.round((shown.days_late + 0.1 * body.delay_days) * 10) / 10,
    };
    return { plan, diff, metrics };
  });
}


interface ScriptStep { text: string; detail?: string; ends?: 'needs'; before?: () => void }
interface Script { steps: ScriptStep[]; actions: UiAction[]; text: string }

let replySeq = 0;
const STEP_MS = 600;

function copilotScript(message: string): Script | null {
  const lower = message.toLowerCase();
  if (lower.includes('rain')) {
    return {
      steps: [
        { text: 'Reading the rain forecast for 14\u201315 Nov', detail: '70 mm in 24 hours \u00b7 simulated' },
        { text: 'Finding works on low-lying roads', detail: 'D-412, P-118, W-118' },
        {
          text: 'Asking the departments to move', detail: 'All 3 agreed in round 1',
          before: () => { void forecastOverride({ kind: 'rain', start_day: 12, end_day: 13, value: 70 }); },
        },
        { text: 'Re-planning with the scheduler', detail: '0 trenches open in the rain' },
        { text: 'Waiting for your approval', ends: 'needs' },
      ],
      actions: [
        { action: 'set_day', args: { day: 12 } },
        { action: 'open_tab', args: { tab: 'risk' } },
        { action: 'show_toast', args: { text: 'Plan updated. 3 works moved out of the rain window.' } },
      ],
      text: 'Rain is coming on 14\u201315 Nov. 3 works moved out of it; the new plan is waiting for your approval.',
    };
  }
  if (lower.includes('munchur')) {
    return {
      steps: [
        { text: 'Finding works on Munchur Road', detail: 'W-104, T-221, G-310, R-501' },
        { text: 'Showing them on the map' },
      ],
      actions: [
        { action: 'open_tab', args: { tab: 'works' } },
        { action: 'select_work', args: { work_id: 'W-104' } },
        { action: 'fit_work', args: { work_id: 'W-104' } },
      ],
      text: '4 works are planned on Munchur Road. W-104 and T-221 share one trench on 10\u201315 Nov.',
    };
  }
  return null;
}

export async function copilot(body: CopilotBody): Promise<CopilotReply> {
  replySeq += 1;
  const reply_id = `RP-${replySeq}`;
  await wait(DELAY_MS);
  const script = copilotScript(body.message);
  if (!script) {
    return {
      reply_id, steps: [], actions: [], used_llm: false,
      text: 'I can show the works on a road, move the day, simulate rain or open a work. Try: show every dig on Munchur Road next week.',
    };
  }
  const steps: CopilotStep[] = [];
  for (const [i, step] of script.steps.entries()) {
    const base = { step_id: `${reply_id}-S${i + 1}`, text: step.text, detail: step.detail ?? null };
    step.before?.();
    emit('copilot.step', { ...base, status: 'running', reply_id });
    await wait(STEP_MS);
    const done: CopilotStep = { ...base, status: step.ends ?? 'done' };
    emit('copilot.step', { ...done, reply_id });
    steps.push(done);
  }
  for (const action of script.actions) emit('ui.action', { ...action, reply_id });
  return copy({ reply_id, text: script.text, steps, actions: script.actions, used_llm: false });
}

// ---------- reads ----------
export function getHealth(): Promise<Health> {
  return reply(() => ({ ok: true, db: false, llm_provider: 'none', weather_mode: 'fixture' }));
}

export function loadScenario(seed: number): Promise<ScenarioLoad> {
  return reply(() => ({
    seed, start_date: SCENARIO.start_date, works: state.works.length, segments: SCENARIO.segments.length,
  }));
}

export function getSegments(bbox?: string): Promise<SegmentCollection> {
  return reply(() => {
    const box = bbox ? bbox.split(',').map(Number) : null;
    const inside = (s: Segment): boolean => !box || box.length !== 4
      || s.coords.some(([lon, lat]) => lon >= box[0] && lat >= box[1] && lon <= box[2] && lat <= box[3]);
    return {
      type: 'FeatureCollection' as const,
      features: SCENARIO.segments.filter(inside).map((s) => ({
        type: 'Feature' as const,
        geometry: { type: 'LineString' as const, coordinates: s.coords },
        properties: {
          segment_id: s.segment_id, name: s.name ?? null, road_class: s.road_class, low_lying: s.low_lying,
          protected_until: s.protected_until ?? null,
        },
      })),
    };
  });
}

export function getDepartments(): Promise<Department[]> {
  return reply(() => DEPARTMENTS);
}

export function getWorks(planId?: string): Promise<WorkView[]> {
  return reply(() => viewsFor(planId ? requirePlan(planId) : shownPlan()));
}

export function getWork(workId: string): Promise<WorkView> {
  return reply(() => {
    const work = requireWork(workId);
    return viewsFor(shownPlan()).find((v) => v.work.work_id === workId) ?? { work, assignment: null, status: statusOf(work, null) };
  });
}

export function addWork(work: Work): Promise<Work> {
  return reply(() => {
    state.works.push(copy(work));
    record(work.dept, 'work.added', `work:${work.work_id}`, `Added ${work.title} on ${work.road_name}`);
    return work;
  });
}

export function planNaive(): Promise<Plan> {
  return reply(() => oldPlan());
}

export function planSolverOnly(): Promise<Plan> {
  return reply(() => {
    const solo: Plan = { ...copy(oldPlan()), plan_id: 'P-SOLO-1', variant: 'solver_only', created_at: demoNow() };
    state.plans = state.plans.filter((p) => p.plan_id !== 'P-SOLO-1');
    state.metrics = state.metrics.filter((m) => m.plan_id !== 'P-SOLO-1');
    state.plans.push(solo);
    state.metrics.push({ ...copy(metricsFor(oldPlan().plan_id) as Metrics), plan_id: 'P-SOLO-1' });
    record('scheduler', 'plan.decided', 'plan:P-SOLO-1', 'Made a plan with the scheduler alone');
    emitPlan(solo);
    return solo;
  });
}

export function getPlans(): Promise<Plan[]> {
  return reply(() => [...state.plans]
    .filter((p) => p.variant !== 'whatif')
    .sort((a, b) => b.created_at.localeCompare(a.created_at)));
}

export function getPlan(planId: string): Promise<Plan> {
  return reply(() => requirePlan(planId));
}

export function getPlanMetrics(planId: string): Promise<Metrics> {
  return reply(() => {
    requirePlan(planId);
    return metricsFor(planId) as Metrics;
  });
}

export function getPlanDiff(planId: string, against = 'naive'): Promise<WorkChange[]> {
  return reply(() => {
    const plan = requirePlan(planId);
    if (against === 'naive' && DIFFS[planId]) return DIFFS[planId];
    return diffPlans(plan, against === 'naive' ? oldPlan() : requirePlan(against));
  });
}

export function getRun(runId: string): Promise<RunResult> {
  return reply(() => {
    const run = state.runs.find((r) => r.run_id === runId);
    if (!run) throw new ApiError(404, `Unknown run ${runId}`);
    return run;
  });
}

export function getNegotiation(runId?: string): Promise<NegotiationMessage[]> {
  return reply(() => {
    const id = runId ?? state.runs[state.runs.length - 1]?.run_id;
    return state.messages.filter((m) => m.run_id === id);
  });
}

export function getRiskWindows(): Promise<RiskWindow[]> {
  return reply(() => state.risk);
}

export function addEvent(body: EventBody): Promise<RiskWindow> {
  return reply(() => {
    const window: RiskWindow = {
      window_id: `EV-${pad(state.nextEvent)}`, kind: 'event', start_day: body.start_day, end_day: body.end_day,
      segment_ids: body.segment_ids, value: 0, source: 'event', label: body.label,
    };
    state.nextEvent += 1;
    state.risk.push(window);
    emit('risk.windows_changed', { windows: state.risk });
    record('system', 'event.added', `plan:${shownPlan().plan_id}`, `Added an event: ${body.label}`);
    return window;
  });
}

export function getApprovals(status?: Approval['status']): Promise<Approval[]> {
  return reply(() => state.approvals.filter((a) => {
    if (status && a.status !== status) return false;
    const planStatus = state.plans.find((p) => p.plan_id === a.plan_id)?.status;
    return !(a.status === 'pending' && planStatus === 'superseded');
  }));
}

export function getLedger(opts: LedgerOpts = {}): Promise<LedgerEntry[]> {
  return reply(() => [...state.ledger]
    .filter((e) => opts.beforeSeq === undefined || e.seq < opts.beforeSeq)
    .sort((a, b) => b.seq - a.seq)
    .slice(0, opts.limit ?? 50));
}

export function verifyLedger(): Promise<LedgerVerify> {
  return reply(() => {
    const entries = state.ledger.length;
    const tampered = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('tampered') === '1';
    return tampered ? { ok: false, entries, first_bad_seq: 126 } : { ok: true, entries };
  });
}

export function getEvidence(workId: string): Promise<Evidence[]> {
  return reply(() => {
    requireWork(workId);
    const list = state.evidence.filter((e) => e.work_id === workId);
    const path = typeof window !== 'undefined' ? window.location.pathname : '';
    if (path.startsWith('/confirm/') || path.endsWith('/result')) {
      // shortcut: screenshot states for the proposal; real photos come from the crew
      const shots: Evidence[] = [
        {
          evidence_id: 'E-0004', work_id: 'W-104', kind: 'after', file_url: PHOTOS.after, lat: 13.0102, lon: 74.7944,
          taken_at: '2026-11-15T17:40:00+05:30', phash: 'c3d81a5e92f4b607', uploaded_at: '2026-11-15T17:40:00+05:30',
        },
        {
          evidence_id: 'E-0005', work_id: 'T-230', kind: 'before', file_url: PHOTOS.before, lat: null, lon: null,
          taken_at: '2026-11-09T08:05:00+05:30', phash: '5f09e7a2c4b81d36', uploaded_at: '2026-11-09T08:05:00+05:30',
        },
      ];
      list.push(...shots.filter((s) => s.work_id === workId));
    }
    return list;
  });
}

export function getVerification(workId: string): Promise<Verification | null> {
  return reply(() => state.verifications.find((v) => v.work_id === workId) ?? null);
}

export function getNoDig(): Promise<NoDigEntry[]> {
  return reply(() => NO_DIG);
}

export function getAuditorFlags(): Promise<AuditorFlag[]> {
  return reply(() => AUDITOR_FLAGS);
}

export function explain(entity: string): Promise<Explanation> {
  return reply(() => {
    const id = entity.includes(':') ? entity.split(':')[1] : entity;
    const plan = state.plans.find((p) => p.plan_id === id);
    if (plan) {
      const rules: Explanation['rules'] = [];
      const reasons = diffPlans(plan, oldPlan()).map((c) => ({
        icon: 'clock', lead: c.title, text: c.reason, source: 'the scheduler, 10:02',
      }));
      return { entity: `plan:${id}`, title: 'Why this plan?', reasons, rules, ledger_seqs: [124] };
    }
    const work = requireWork(id);
    const found = explainWork(id, shownPlan().plan_id);
    if (found) return found;
    const assignment = shownPlan().assignments.find((a) => a.work_id === id);
    return {
      entity: `work:${id}`,
      title: 'Why these dates?',
      reasons: [{
        icon: 'clock', lead: assignment ? `Runs ${dayRange(assignment.start_day, assignment.end_day)}.` : `${work.title} is not planned yet.`,
        text: assignment?.reason ?? '', source: 'the rules, 09:14',
      }],
      rules: [{ name: 'Emergency dig allowed at once', severity: 'ok' as const, detail: work.title }],
      ledger_seqs: [119, 120],
    };
  });
}

export function getEvalsSummary(): Promise<EvalSummary> {
  return reply(() => EVAL_SUMMARY);
}