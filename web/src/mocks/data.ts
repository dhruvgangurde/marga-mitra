// Plain typed demo data for the mock layer. Day 0 is 2 Nov 2026, today is day 8 (10 Nov),
// and the demo clock runs 09:00–10:06 IST. Screens never import this file; they use api/hooks.ts.
import beforePhoto from './photos/before.jpg';
import afterPhoto from './photos/after.jpg';
import scenarioJson from './scenario.json';
import { dayRange, inr } from '../api/format';
import type {
  Approval, Assignment, AuditorFlag, CheckName, CheckStatus, Department, Dept, EvalRow, EvalSummary, Evidence,
  Explanation, LedgerEntry, Metrics, Mode, NegotiationMessage, NegotiationOption, NoDigEntry, Plan, RiskWindow,
  RuleCheck, Scenario, Sender, Stat, MessageType, Verification, VerificationCheck, Work, WorkChange,
} from '../api/types';

export const PHOTOS = { before: beforePhoto, after: afterPhoto };
export const SCENARIO = scenarioJson as unknown as Scenario;

const IST = '+05:30';
const at = (date: string, time: string): string => `${date}T${time}${IST}`;
const nov10 = (time: string): string => at('2026-11-10', time);

// ---------- works ----------
const RATES: Record<Dept, number> = { water: 3800, drainage: 4200, gas: 3000, power: 2600, telecom: 1500, roads: 900 };

function roundTo(n: number, step: number): number {
  return Math.round(n / step) * step;
}

function openCutCost(dept: Dept, length: number): number {
  return roundTo(RATES[dept] * length + length * 0.9 * 1200, 100);
}

function trenchlessCost(dept: Dept, length: number): number {
  return roundTo(RATES[dept] * length * 1.8 + Math.max(2, Math.floor(length / 60) + 1) * 2 * 1200, 100);
}

interface WorkRow {
  id: string;
  dept: Dept;
  title: string;
  road: string;
  length: number;
  mode: Mode;
  alsoTrenchless?: boolean;
  start: number;
  days: number;
  dependsOn?: string[];
  done?: boolean;
}

const ROWS: WorkRow[] = [
  { id: 'W-104', dept: 'water', title: 'Water main', road: 'Munchur Road', length: 620, mode: 'open_cut', start: 7, days: 6 },
  { id: 'T-221', dept: 'telecom', title: 'Fibre duct', road: 'Munchur Road', length: 620, mode: 'open_cut', alsoTrenchless: true, start: 10, days: 4 },
  { id: 'G-310', dept: 'gas', title: 'Gas line', road: 'Munchur Road east', length: 480, mode: 'open_cut', start: 8, days: 5 },
  { id: 'R-501', dept: 'roads', title: 'Resurfacing', road: 'Munchur Road', length: 1100, mode: 'open_cut', start: 9, days: 4, dependsOn: ['W-104', 'T-221', 'G-310'] },
  { id: 'D-412', dept: 'drainage', title: 'Storm-water drain', road: 'NH-66 service road', length: 300, mode: 'open_cut', start: 11, days: 4 },
  { id: 'P-118', dept: 'power', title: 'Cable shifting', road: 'Krishnapura cross road', length: 210, mode: 'open_cut', start: 11, days: 3 },
  { id: 'W-118', dept: 'water', title: 'Service line', road: 'Idya lane', length: 90, mode: 'open_cut', start: 12, days: 2 },
  { id: 'T-230', dept: 'telecom', title: 'Fibre to tower', road: 'Hosabettu cross road', length: 350, mode: 'trenchless', start: 7, days: 3 },
  { id: 'D-415', dept: 'drainage', title: 'Drain repair', road: 'Chokkabettu lane', length: 140, mode: 'open_cut', start: 0, days: 4, done: true },
  { id: 'P-120', dept: 'power', title: 'Streetlight cable', road: 'NITK Beach Road', length: 400, mode: 'trenchless', start: 14, days: 3 },
  { id: 'G-305', dept: 'gas', title: 'Service connections', road: 'Hosabettu Road', length: 260, mode: 'trenchless', start: 5, days: 3, done: true },
  { id: 'W-109', dept: 'water', title: 'Valve replacement', road: 'Srinivasnagar road', length: 120, mode: 'open_cut', start: 3, days: 2, done: true },
  { id: 'D-420', dept: 'drainage', title: 'Culvert cleaning', road: 'Katipalla road', length: 180, mode: 'open_cut', start: 16, days: 3 },
  { id: 'T-240', dept: 'telecom', title: 'Fibre duct', road: 'Kana road', length: 500, mode: 'open_cut', start: 15, days: 4 },
  { id: 'R-505', dept: 'roads', title: 'Pothole patching', road: 'Surathkal market road', length: 300, mode: 'open_cut', start: 20, days: 2 },
  { id: 'P-125', dept: 'power', title: 'Transformer cable', road: 'Kulai road', length: 150, mode: 'open_cut', start: 6, days: 2, done: true },
];

function buildWork(r: WorkRow): Work {
  const open = {
    mode: 'open_cut' as Mode,
    duration_days: r.days,
    cost_inr: openCutCost(r.dept, r.length),
    lanes_closed: r.id === 'R-501' ? 2 : 1,
    dust: 0.6,
  };
  const trenchless = (days: number) => ({
    mode: 'trenchless' as Mode,
    duration_days: days,
    cost_inr: trenchlessCost(r.dept, r.length),
    lanes_closed: 0,
    dust: 0,
  });
  const modes = r.mode === 'trenchless' ? [trenchless(r.days)] : r.alsoTrenchless ? [open, trenchless(r.days + 1)] : [open];
  return {
    work_id: r.id,
    dept: r.dept,
    title: r.title,
    road_name: r.road,
    segment_ids: [],
    length_m: r.length,
    requested_start: r.start,
    earliest_start: r.id === 'T-221' ? 8 : r.start,
    latest_end: 27,
    modes,
    priority: r.id === 'W-104' ? 4 : 3,
    depends_on: r.dependsOn ?? [],
    deposit_inr: r.id === 'W-104' ? 240000 : Math.max(10000, roundTo(modes[0].cost_inr * 0.1, 10000)),
    is_emergency: false,
    done: r.done ?? false,
  };
}

export const WORKS: Work[] = ROWS.map(buildWork);
const workById = (id: string): Work => WORKS.find((w) => w.work_id === id) as Work;

// ---------- plans ----------
const CREATED_OLD = nov10('09:00:00');

function oldAssignment(w: Work): Assignment {
  const m = w.modes[0];
  return {
    work_id: w.work_id,
    start_day: w.requested_start,
    end_day: w.requested_start + m.duration_days - 1,
    mode: m.mode,
    shared_group: null,
    reason: 'As the department asked.',
  };
}

function asg(id: string, start: number, end: number, reason: string, group: string | null = null): Assignment {
  return { work_id: id, start_day: start, end_day: end, mode: 'open_cut', shared_group: group, reason };
}

function replaceAssignments(base: Assignment[], changes: Assignment[]): Assignment[] {
  const byId = new Map(changes.map((a) => [a.work_id, a]));
  return base.map((a) => byId.get(a.work_id) ?? a);
}

const OLD_ASSIGNMENTS = WORKS.map(oldAssignment);
const P0007_CHANGES: Assignment[] = [
  asg('W-104', 8, 13, 'Shares one trench with Telecom T-221.', 'G1'),
  asg('T-221', 8, 13, 'Joins the shared trench: no second dig.', 'G1'),
  asg('G-310', 14, 18, 'Starts after the trench is closed.'),
  asg('R-501', 22, 25, 'Resurfaces after every dig on the road.'),
];
const P0008_CHANGES: Assignment[] = [
  asg('D-412', 14, 17, 'Moved after the rain: the road is low-lying.'),
  asg('P-118', 19, 21, 'Moved after the rain and after D-412 at the same junction.'),
  asg('W-118', 19, 20, 'Moved after the rain and after the procession on 20 Nov.'),
];
const P0007_ASSIGNMENTS = replaceAssignments(OLD_ASSIGNMENTS, P0007_CHANGES);
const P0008_ASSIGNMENTS = replaceAssignments(P0007_ASSIGNMENTS, P0008_CHANGES);

function plan(
  id: string, variant: Plan['variant'], status: Plan['status'], created: string, assignments: Assignment[],
  solveMs: number, base: string | null,
): Plan {
  return {
    plan_id: id, seed: 1, variant, status, created_at: created, assignments, unplanned: [], notes: [],
    objective: 0, solve_ms: solveMs, base_plan_id: base,
  };
}

export const PLANS: Plan[] = [
  plan('P-OLD-1', 'naive', 'draft', CREATED_OLD, OLD_ASSIGNMENTS, 0, null),
  plan('P-0007', 'orchestrated', 'waiting_approval', nov10('10:02:23'), P0007_ASSIGNMENTS, 3100, 'P-OLD-1'),
  plan('P-0008', 'orchestrated', 'waiting_approval', nov10('10:05:58'), P0008_ASSIGNMENTS, 4200, 'P-0007'),
];

// ---------- metrics ----------
export const RAIN_TRENCH_HOURS = 96; // old-way trench-hours in rain once the heavy-rain window is on

export const METRICS: Metrics[] = [
  {
    plan_id: 'P-OLD-1', digs_per_road: 3.4, lane_closure_hours: 1096, clashes: 7, trench_hours_in_rain: 0,
    days_late: 0, excavations: 15, cost_inr: 4988000, dust_score: 9.0,
  },
  {
    plan_id: 'P-0007', digs_per_road: 1.6, lane_closure_hours: 530, clashes: 1, trench_hours_in_rain: 0,
    days_late: 0.4, excavations: 13, cost_inr: 4590000, dust_score: 7.8,
  },
  {
    plan_id: 'P-0008', digs_per_road: 1.3, lane_closure_hours: 412, clashes: 0, trench_hours_in_rain: 0,
    days_late: 0.6, excavations: 13, cost_inr: 4602500, dust_score: 7.8,
  },
];

// ---------- changes against the old way ----------
const COST_DELTAS: Record<string, number> = {
  'W-104': 38000, 'T-221': -164000, 'G-310': 0, 'R-501': -210000, 'D-412': 6000, 'P-118': 4500, 'W-118': 2000,
};

function changeFor(a: Assignment): WorkChange {
  const w = workById(a.work_id);
  const old = OLD_ASSIGNMENTS.find((o) => o.work_id === a.work_id) as Assignment;
  return {
    work_id: w.work_id,
    dept: w.dept,
    title: `${w.title}, ${w.road_name} · ${w.work_id}`,
    from_start: old.start_day,
    from_end: old.end_day,
    to_start: a.start_day,
    to_end: a.end_day,
    mode_from: old.mode,
    mode_to: a.mode,
    shared_group: a.shared_group ?? null,
    reason: a.reason,
    cost_delta_inr: COST_DELTAS[a.work_id],
  };
}

export const DIFFS: Record<string, WorkChange[]> = {
  'P-0007': P0007_CHANGES.map(changeFor),
  'P-0008': [...P0007_CHANGES, ...P0008_CHANGES].map(changeFor),
};

// ---------- negotiation ----------
interface MsgInput {
  id: string;
  run: string;
  round: number;
  sender: Sender;
  to: string[];
  type: MessageType;
  works: string[];
  time: string;
  body: string;
  options?: NegotiationOption[];
  chosen?: number | null;
}

function msg(p: MsgInput): NegotiationMessage {
  return {
    msg_id: p.id, run_id: p.run, round: p.round, sender: p.sender, recipients: p.to, type: p.type,
    work_ids: p.works, body: p.body, options: p.options ?? [], chosen_option: p.chosen ?? null, ts: nov10(p.time),
  };
}

const RUN7_WORKS = ['W-104', 'T-221', 'G-310', 'R-501'];

export const MESSAGES_RUN_0007: NegotiationMessage[] = [
  msg({
    id: 'M11', run: 'RUN-0007', round: 1, sender: 'coordinator', to: ['water', 'telecom', 'gas', 'roads'], type: 'NOTICE',
    works: RUN7_WORKS, time: '10:02:11',
    body: '4 works clash on Munchur Road between 9 and 15 Nov: W-104, T-221, G-310 and R-501.',
  }),
  msg({
    id: 'M12', run: 'RUN-0007', round: 1, sender: 'water', to: ['coordinator'], type: 'COUNTER',
    works: ['W-104', 'T-221'], time: '10:02:14', chosen: 0,
    body: 'W-104 can share one trench with T-221 if it starts on 10 Nov. It cannot start after 12 Nov.',
    options: [
      { label: 'A · Shared trench, 10–15 Nov', work_id: 'W-104', start_day: 8, mode: 'open_cut', shared_group: 'G1', cost_delta_inr: 38000 },
      { label: 'B · Water first, Telecom after', work_id: 'W-104', start_day: 8, mode: 'open_cut', shared_group: null, cost_delta_inr: 120000 },
    ],
  }),
  msg({
    id: 'M13', run: 'RUN-0007', round: 1, sender: 'telecom', to: ['coordinator'], type: 'ACCEPT',
    works: ['T-221'], time: '10:02:16', body: 'T-221 joins the shared trench, 10–15 Nov.',
  }),
  msg({
    id: 'M21', run: 'RUN-0007', round: 2, sender: 'gas', to: ['coordinator'], type: 'COUNTER',
    works: ['G-310'], time: '10:02:19', chosen: 0,
    body: 'G-310 is on the east stretch. It can move to 16–20 Nov, after the trench is closed.',
    options: [
      { label: 'A · Move to 16–20 Nov', work_id: 'G-310', start_day: 14, mode: 'open_cut', shared_group: null, cost_delta_inr: 0 },
    ],
  }),
  msg({
    id: 'M22', run: 'RUN-0007', round: 2, sender: 'roads', to: ['coordinator'], type: 'ACCEPT',
    works: ['R-501'], time: '10:02:21',
    body: 'R-501 resurfaces after every dig, 24–27 Nov. The road is then protected for 3 years.',
  }),
  msg({
    id: 'M23', run: 'RUN-0007', round: 2, sender: 'solver', to: ['everyone'], type: 'DECISION',
    works: RUN7_WORKS, time: '10:02:23',
    body: 'Option A. Munchur Road: 4 digs become 2, lane-closure hours 410 → 150.',
  }),
];

const RAIN_WORKS = ['D-412', 'P-118', 'W-118'];

export const MESSAGES_RUN_0008: NegotiationMessage[] = [
  msg({
    id: 'M31', run: 'RUN-0008', round: 1, sender: 'coordinator', to: ['drainage', 'power', 'water'], type: 'NOTICE',
    works: RAIN_WORKS, time: '10:05:41',
    body: 'Heavy rain is forecast for 14–15 Nov. D-412, P-118 and W-118 are open on low-lying roads then.',
  }),
  msg({
    id: 'M32', run: 'RUN-0008', round: 1, sender: 'drainage', to: ['coordinator'], type: 'ACCEPT',
    works: ['D-412'], time: '10:05:46', body: 'D-412 moves to 16–19 Nov, after the rain.',
  }),
  msg({
    id: 'M33', run: 'RUN-0008', round: 1, sender: 'power', to: ['coordinator'], type: 'ACCEPT',
    works: ['P-118'], time: '10:05:50', body: 'P-118 moves to 21–23 Nov, after D-412 at the same junction.',
  }),
  msg({
    id: 'M34', run: 'RUN-0008', round: 1, sender: 'water', to: ['coordinator'], type: 'ACCEPT',
    works: ['W-118'], time: '10:05:54', body: 'W-118 moves to 21–22 Nov, after the procession on 20 Nov.',
  }),
  msg({
    id: 'M35', run: 'RUN-0008', round: 1, sender: 'solver', to: ['everyone'], type: 'DECISION',
    works: RAIN_WORKS, time: '10:05:58', body: '3 works moved out of the rain. Trench-hours in rain: 96 → 0.',
  }),
];

// ---------- approvals ----------
function pending(id: string, planId: string, runId: string, time: string): Approval {
  return {
    approval_id: id, plan_id: planId, run_id: runId, tier: 'ward_engineer', status: 'pending',
    summary: 'New plan for 2–29 Nov', requested_at: nov10(time), decided_at: null, decided_by: null, reason: null,
  };
}

export const APPROVALS: Approval[] = [
  pending('A-0001', 'P-0007', 'RUN-0007', '10:02:23'),
  pending('A-0002', 'P-0008', 'RUN-0008', '10:05:58'),
];

export const APPROVAL_HISTORY: Approval[] = [
  {
    approval_id: 'A-0000', plan_id: 'P-0006', run_id: 'RUN-0006', tier: 'ward_engineer', status: 'approved',
    summary: 'Plan for 26 Oct – 22 Nov', requested_at: at('2026-10-26', '17:35:00'),
    decided_at: at('2026-10-26', '17:40:00'), decided_by: 'ward_engineer', reason: null,
  },
];

export const EMERGENCY_LINE = {
  title: 'Emergency dig, Idya Road',
  text: 'Burst water pipe · allowed at once by the rules · 09:14',
};

// ---------- risk windows ----------
// Segment ids of EV-DEMO (EVENT_ROADS) and OV-1 (OV_1_WORK_IDS) are filled by the mock server from the works and roads.
export const EVENT_ROADS = ['NH-66 service road', 'Idya lane'];
export const OV_1_WORK_IDS = RAIN_WORKS;

export const EVENT_DETAILS: Record<string, string> = {
  'EV-DEMO': 'NH-66 service road and Idya lane · closed 16:00–22:00',
};

export const RISK_WINDOWS: RiskWindow[] = [
  {
    window_id: 'EV-DEMO', kind: 'event', start_day: 18, end_day: 18, segment_ids: [], value: 0,
    source: 'event', label: 'Procession, 20 Nov',
  },
  {
    window_id: 'A1', kind: 'air', start_day: 26, end_day: 27, segment_ids: SCENARIO.segments.map((s) => s.segment_id),
    value: 205, source: 'fixture', label: 'Poor air, 28–29 Nov',
  },
];

export const OV_1: RiskWindow = {
  window_id: 'OV-1', kind: 'rain', start_day: 12, end_day: 13, segment_ids: [], value: 70,
  source: 'override', label: 'Heavy rain, 14–15 Nov',
};

export const FORECAST_SUMMARY = { max_rain_mm: 18, max_aqi: 88, band: 'Satisfactory' };

// ---------- Why? ----------
function rulesFor(w: Work, a: Assignment): RuleCheck[] {
  return [
    { name: 'Road is not protected', severity: 'ok', detail: `${w.road_name} is not in the protected-road list` },
    { name: 'Deposit held until the repair is verified', severity: 'ok', detail: inr(w.deposit_inr) },
    { name: `No heavy rain forecast for ${dayRange(a.start_day, a.end_day)}`, severity: 'ok', detail: 'Highest: 18 mm in 24 hours' },
    { name: 'Air quality is fine for open cuts', severity: 'ok', detail: 'AQI 88 · Satisfactory' },
  ];
}

export function explainWork(workId: string, planId = 'P-0008'): Explanation | null {
  const w = WORKS.find((x) => x.work_id === workId);
  const p = PLANS.find((x) => x.plan_id === planId);
  const a = p?.assignments.find((x) => x.work_id === workId);
  if (!w || !a) return null;
  if (workId === 'W-104') {
    return {
      entity: 'work:W-104',
      title: 'Why these dates?',
      reasons: [
        {
          icon: 'handshake', lead: 'Shares one trench with Telecom (T-221).', text: 'One dig instead of two on the same 620 m.',
          source: 'negotiation, round 1, 10:02:16',
        },
        {
          icon: 'clock', lead: 'Starts on 10 Nov, not 9 Nov.', text: 'The Telecom crew is free from 10 Nov.',
          source: 'Telecom, round 1',
        },
        {
          icon: 'road', lead: 'Ends before resurfacing on 24 Nov.', text: 'The new surface is never cut.',
          source: 'rule: no new digs for 3 years after resurfacing',
        },
      ],
      rules: [
        { name: 'Road is not protected', severity: 'ok', detail: 'Munchur Road is not in the protected-road list' },
        { name: 'Deposit held until the repair is verified', severity: 'ok', detail: '₹2,40,000' },
        { name: 'No heavy rain forecast for 10–15 Nov', severity: 'ok', detail: 'Highest: 18 mm in 24 hours' },
        { name: 'Air quality is fine for open cuts', severity: 'ok', detail: 'AQI 88 · Satisfactory' },
      ],
      ledger_seqs: [124, 127, 128],
    };
  }
  return {
    entity: `work:${workId}`,
    title: 'Why these dates?',
    reasons: [{ icon: 'clock', lead: `Runs ${dayRange(a.start_day, a.end_day)}.`, text: a.reason, source: 'the scheduler, 10:02' }],
    rules: rulesFor(w, a),
    ledger_seqs: [],
  };
}

// ---------- public record ----------
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fakeHash(seq: number, head = '', tail = ''): string {
  const next = rng(seq * 7919);
  let middle = '';
  while (middle.length < 64 - head.length - tail.length) middle += Math.floor(next() * 16).toString(16);
  return head + middle + tail;
}

const HISTORY_ROADS = ['Munchur Road', 'NH-66 service road', 'Hosabettu Road', 'Idya lane', 'Krishnapura cross road'];
const HISTORY_WINDOWS = ['19 Oct – 15 Nov', '26 Oct – 22 Nov'];
const HISTORY_START = Date.parse('2026-10-20T09:00:00+05:30');
const HISTORY_STEP_MS = 254 * 60 * 1000;

function istIso(ms: number): string {
  return new Date(ms + 5.5 * 3600 * 1000).toISOString().slice(0, 19) + IST;
}

interface Draft {
  ts: string;
  actor: string;
  action: string;
  entity: string;
  summary: string;
  head?: string;
  tail?: string;
}

function historyDraft(seq: number): Draft {
  const road = HISTORY_ROADS[seq % HISTORY_ROADS.length];
  const window = HISTORY_WINDOWS[seq % HISTORY_WINDOWS.length];
  const planId = `plan:P-${String((seq % 6) + 1).padStart(4, '0')}`;
  const workId = `work:${WORKS[seq % WORKS.length].work_id}`;
  const ts = istIso(HISTORY_START + (seq - 1) * HISTORY_STEP_MS);
  switch (seq % 5) {
    case 0: return { ts, actor: 'scheduler', action: 'plan.decided', entity: planId, summary: `Decided the plan for ${road}` };
    case 1: return { ts, actor: 'rules', action: 'rules.passed', entity: planId, summary: 'Passed: no protected road is dug, every deposit is held' };
    case 2: return { ts, actor: 'ward_engineer', action: 'plan.approved', entity: planId, summary: `Approved the plan for ${window}` };
    case 3: return { ts, actor: 'photo_check', action: 'verification.verified', entity: workId, summary: 'Repair verified: money released' };
    default: return { ts, actor: 'resident', action: 'report.confirmed', entity: workId, summary: 'Confirmed the road is restored' };
  }
}

const TODAY_DRAFTS: Draft[] = [
  { ts: nov10('09:14:02'), actor: 'resident', action: 'report.added', entity: 'work:W-131', summary: 'Reported a burst water pipe on Idya Road', head: 'f1c0', tail: '6a3e' },
  { ts: nov10('09:14:30'), actor: 'rules', action: 'rules.passed', entity: 'work:W-131', summary: 'Emergency dig allowed at once: burst water pipe', head: '2d5a', tail: '8cf1' },
  { ts: nov10('09:41:07'), actor: 'photo_check', action: 'verification.held', entity: 'work:T-230', summary: 'Photo reused from T-221: money held, inspector called', head: 'a4e9', tail: '37b2' },
  { ts: nov10('10:02:19'), actor: 'gas', action: 'negotiation.counter', entity: 'work:G-310', summary: 'Asked to move to 16–20 Nov', head: '66c4', tail: 'd0e5' },
  { ts: nov10('10:02:21'), actor: 'roads', action: 'negotiation.accept', entity: 'work:R-501', summary: 'Agreed to resurface on 24–27 Nov', head: '0b77', tail: 'a812' },
  { ts: nov10('10:02:23'), actor: 'scheduler', action: 'plan.decided', entity: 'work:W-104', summary: 'Decided Munchur Road: 4 digs become 2', head: '3f9a', tail: 'c21e' },
  { ts: nov10('10:05:41'), actor: 'forecast', action: 'forecast.changed', entity: 'plan:P-0008', summary: 'Heavy rain 14–15 Nov (simulated for the demo)', head: 'e83b', tail: '1f90' },
  { ts: nov10('10:05:58'), actor: 'scheduler', action: 'plan.decided', entity: 'work:D-412', summary: 'Re-planned after the rain forecast: 3 works moved', head: '7a2f', tail: '0c3d' },
  { ts: nov10('10:06:12'), actor: 'rules', action: 'rules.passed', entity: 'plan:P-0008', summary: 'Passed: no protected road is dug, every deposit is held', head: '51d0', tail: '9e27' },
  { ts: nov10('10:06:40'), actor: 'ward_engineer', action: 'plan.approved', entity: 'plan:P-0008', summary: 'Approved the plan for 2–29 Nov', head: '9c1e', tail: '44ab' },
];

function buildLedger(): LedgerEntry[] {
  const drafts: Draft[] = [];
  for (let seq = 1; seq <= 118; seq += 1) drafts.push(historyDraft(seq));
  drafts.push(...TODAY_DRAFTS);
  const entries: LedgerEntry[] = [];
  let prev = '0'.repeat(64);
  drafts.forEach((d, i) => {
    const seq = i + 1;
    const hash = fakeHash(seq, d.head, d.tail);
    entries.push({
      seq, ts: d.ts, actor: d.actor, action: d.action, entity: d.entity, summary: d.summary,
      payload: {}, prev_hash: prev, hash,
    });
    prev = hash;
  });
  return entries;
}

export const LEDGER: LedgerEntry[] = buildLedger();

// ---------- protected roads ----------
function firstSegmentOn(road: string): string {
  const seg = SCENARIO.segments.find((s) => (s.name ?? '').toLowerCase() === road.toLowerCase());
  return seg ? seg.segment_id : 'S-0000';
}

export const NO_DIG: NoDigEntry[] = [
  { road: 'Hosabettu Road', until: '2029-03-03', why: 'Resurfaced on 3 Mar 2026' },
  { road: 'NITK Beach Road', until: '2028-01-14', why: 'Concreted on 14 Jan 2025' },
  { road: 'Munchur Road', until: '2029-11-27', why: 'From the planned resurfacing R-501' },
].map((r) => ({ segment_id: firstSegmentOn(r.road), name: r.road, protected_until: r.until, why: r.why }));

// ---------- auditor ----------
export const AUDITOR_FLAGS: AuditorFlag[] = [
  {
    flag_id: 'F-0001', severity: 'fail', word: 'Photo reused', work_id: 'T-230', ledger_seq: 121, created_at: nov10('09:41:00'),
    text: 'The after photo of T-230 is the same as the before photo of T-221 (96% alike). Money is held and an inspector visits on 12 Nov.',
  },
  {
    flag_id: 'F-0002', severity: 'warn', word: 'Look again', work_id: 'G-310', ledger_seq: 122, created_at: nov10('10:02:00'),
    text: 'Gas work G-310 was moved twice in 3 days. Ask the Gas department if its crew is free on 16 Nov.',
  },
  {
    flag_id: 'F-0003', severity: 'ok', word: 'Reviewed', work_id: 'W-131', ledger_seq: 120, created_at: nov10('09:40:00'),
    text: 'Emergency dig W-131 started before approval, as the rules allow. The ward engineer reviewed it at 09:40.',
  },
];

// ---------- photos and checks ----------
const SAME_PHOTO_HASH = 'b27f60d19ac3e458';

export const EVIDENCE: Evidence[] = [
  {
    evidence_id: 'E-0001', work_id: 'W-104', kind: 'before', file_url: beforePhoto, lat: 13.0101, lon: 74.7943,
    taken_at: nov10('08:12:00'), phash: 'e1a4c93b7d205f68', uploaded_at: nov10('08:12:00'),
  },
  {
    evidence_id: 'E-0002', work_id: 'T-221', kind: 'before', file_url: beforePhoto, taken_at: nov10('08:20:00'),
    phash: SAME_PHOTO_HASH, uploaded_at: nov10('08:20:00'),
  },
  {
    evidence_id: 'E-0003', work_id: 'T-230', kind: 'after', file_url: beforePhoto, taken_at: nov10('09:40:00'),
    phash: SAME_PHOTO_HASH, uploaded_at: nov10('09:40:00'),
  },
];

function check(name: CheckName, status: CheckStatus, detail: string): VerificationCheck {
  return { name, status, detail };
}

export function verifiedChecks(): VerificationCheck[] {
  return [
    check('place', 'ok', 'Both photos within 12 m of the site'),
    check('time', 'ok', 'Taken between 10 and 15 Nov'),
    check('reuse', 'ok', 'Not seen in any other work'),
    check('repair', 'ok', 'Trench closed, surface patched, no debris'),
    check('resident', 'ok', 'Confirmed the road is restored, 16 Nov'),
    check('inspection', 'pending', '1 in 10 works is visited'),
  ];
}

export function inspectChecks(): VerificationCheck[] {
  return verifiedChecks().map((c) => {
    if (c.name === 'repair') return check('repair', 'warn', 'The after photo is too dark to judge');
    if (c.name === 'resident') return check('resident', 'pending', 'Asked on 15 Nov');
    return c;
  });
}

export const VERIFICATIONS: Verification[] = [
  {
    verification_id: 'V-0001', work_id: 'T-230', result: 'held', deposit_inr: workById('T-230').deposit_inr,
    deposit_released: false, decided_at: nov10('09:41:07'),
    checks: [
      check('place', 'ok', 'Both photos within 9 m of the site'),
      check('time', 'ok', 'Taken between 9 and 11 Nov'),
      check('reuse', 'fail', 'Same as the before photo of T-221 (96% alike)'),
      check('repair', 'pending', 'Waiting for the inspector'),
      check('resident', 'pending', 'Asked on 10 Nov'),
      check('inspection', 'pending', 'Inspector visits on 12 Nov'),
    ],
  },
];

// ---------- evals ----------
const stat = (median: number, low: number, high: number): Stat => ({ median, low, high });

function evalRow(variant: EvalRow['variant'], v: [Stat, Stat, Stat, Stat, Stat, Stat]): EvalRow {
  return {
    variant, digs_per_road: v[0], lane_closure_hours: v[1], trench_hours_in_rain: v[2], clashes: v[3], days_late: v[4],
    cost_inr: v[5],
  };
}

const RISK_ROW: [Stat, Stat, Stat, Stat, Stat, Stat] = [
  stat(1.3, 1.1, 1.7), stat(412, 350, 520), stat(2, 0, 12), stat(0, 0, 1), stat(0.6, 0.2, 1.1),
  stat(4602500, 3800000, 5400000),
];

export const EVAL_SUMMARY: EvalSummary = {
  seeds: Array.from({ length: 50 }, (_, i) => i + 1),
  rows: [
    evalRow('naive', [
      stat(3.4, 2.9, 4.1), stat(1096, 870, 1410), stat(96, 40, 180), stat(7.2, 5, 11), stat(0, 0, 0),
      stat(4988000, 4100000, 5800000),
    ]),
    evalRow('solver_only', [
      stat(1.9, 1.6, 2.4), stat(640, 520, 790), stat(61, 20, 130), stat(0.4, 0, 2), stat(0.2, 0, 0.6),
      stat(4710000, 3900000, 5500000),
    ]),
    evalRow('agents', [
      stat(1.4, 1.2, 1.8), stat(455, 380, 560), stat(61, 20, 130), stat(0, 0, 1), stat(0.4, 0.1, 0.9),
      stat(4590000, 3800000, 5400000),
    ]),
    evalRow('risk', RISK_ROW),
    evalRow('full', RISK_ROW),
  ],
  fake_repairs_caught: 9,
  fake_repairs_total: 10,
  generated_at: at('2026-10-21', '08:00:00'),
};

// ---------- departments ----------
const DEPT_ROWS: [Dept, string, string][] = [
  ['water', 'Water', 'drop'],
  ['drainage', 'Drainage', 'waves'],
  ['gas', 'Gas', 'flame'],
  ['power', 'Power', 'lightning'],
  ['telecom', 'Telecom', 'wifi'],
  ['roads', 'Roads', 'road'],
];

export const DEPARTMENTS: Department[] = DEPT_ROWS.map(([id, name, icon]) => ({
  id, name, icon, color_token: `--dept-${id}`,
}));