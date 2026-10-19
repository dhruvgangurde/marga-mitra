// Every date, time and money string on screen comes from here.
// Pure functions with no run-time imports, so node can run scripts/check-format.ts directly.
import type { Mode, WorkStatus } from './types';

const MINUS = '\u2212';
const DASH = '\u2013';
const TZ = 'Asia/Kolkata';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const START_DATE = '2026-11-02';
export const TODAY_DAY = 8;

// ---------- money ----------
function groupIndian(n: number): string {
  return Math.round(Math.abs(n)).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

export function inr(n: number): string {
  return (n < 0 ? MINUS : '') + '₹' + groupIndian(n);
}

export function signedInr(n: number): string {
  return (n < 0 ? MINUS : '+') + '₹' + groupIndian(n);
}

// ---------- days ----------
export function dayDate(day: number): Date {
  const d = new Date(START_DATE + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + day);
  return d;
}

export function dayLabel(day: number): string {
  const d = dayDate(day);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

export function dayRange(start: number, end: number): string {
  if (start === end) return dayLabel(start);
  const a = dayDate(start);
  const b = dayDate(end);
  if (a.getUTCMonth() === b.getUTCMonth()) {
    return `${a.getUTCDate()}${DASH}${b.getUTCDate()} ${MONTHS[b.getUTCMonth()]}`;
  }
  return `${dayLabel(start)} ${DASH} ${dayLabel(end)}`;
}

// ---------- clock times (always shown in IST) ----------
function istParts(iso: string): Record<string, string> {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: TZ,
    day: 'numeric',
    month: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const out: Record<string, string> = {};
  for (const p of parts) out[p.type] = p.value;
  return out;
}

export function timeLabel(iso: string): string {
  const p = istParts(iso);
  return `${p.hour}:${p.minute}:${p.second}`;
}

export function shortTime(iso: string): string {
  const p = istParts(iso);
  return `${p.hour}:${p.minute}`;
}

export function dateTimeLabel(iso: string): string {
  const p = istParts(iso);
  return `${Number(p.day)} ${MONTHS[Number(p.month) - 1]}, ${p.hour}:${p.minute}`;
}

// ---------- lengths and links ----------
export function metres(m: number): string {
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m / 1000).toFixed(1).replace(/\.0$/, '')} km`;
}

export function linkLabel(hash: string): string {
  return `${hash.slice(0, 4)}…${hash.slice(-4)}`;
}

// ---------- names ----------
const DEPT_NAMES: Record<string, string> = {
  water: 'Water',
  drainage: 'Drainage',
  gas: 'Gas',
  power: 'Power',
  telecom: 'Telecom',
  roads: 'Roads',
  coordinator: 'Coordinator',
  solver: 'Scheduler',
};

export function deptName(id: string): string {
  return DEPT_NAMES[id] ?? id;
}

const ACTOR_NAMES: Record<string, string> = {
  scheduler: 'Scheduler',
  rules: 'Rules check',
  ward_engineer: 'Ward engineer',
  department_officer: 'Department officer',
  forecast: 'Forecast check',
  photo_check: 'Photo check',
  resident: 'Resident',
  auditor: 'Auditor',
  coordinator: 'Coordinator',
  system: 'MargaMitra',
};

export function actorLabel(actor: string): string {
  return ACTOR_NAMES[actor] ?? DEPT_NAMES[actor] ?? actor;
}

export function methodLabel(mode: Mode): string {
  return mode === 'trenchless' ? 'trenchless' : 'open cut';
}

export function aqiBand(aqi: number): string {
  if (aqi <= 50) return 'Good';
  if (aqi <= 100) return 'Satisfactory';
  if (aqi <= 200) return 'Moderate';
  if (aqi <= 300) return 'Poor';
  if (aqi <= 400) return 'Very poor';
  return 'Severe';
}

// ---------- badges and metrics ----------
export type BadgeStatus = 'ok' | 'fail' | 'warn' | 'pending' | 'approved' | 'live' | 'emergency';

const WORK_BADGES: Record<WorkStatus, { status: BadgeStatus; label: string }> = {
  planned: { status: 'pending', label: 'Planned' },
  moved: { status: 'warn', label: 'Moved' },
  shared: { status: 'approved', label: 'Shared trench' },
  digging: { status: 'live', label: 'Digging' },
  done: { status: 'ok', label: 'Done' },
  verified: { status: 'ok', label: 'Verified' },
  held: { status: 'fail', label: 'Money held' },
  emergency: { status: 'emergency', label: 'Emergency' },
};

export function workStatusBadge(status: WorkStatus): { status: BadgeStatus; label: string } {
  return WORK_BADGES[status];
}

export type MetricKind = 'digs_per_road' | 'lane_closure_hours' | 'clashes' | 'trench_hours_in_rain' | 'days_late';

export function metricDelta(now: number, old: number, kind: MetricKind): { delta?: string; better: boolean } {
  const better = now <= old;
  if (now === 0 && old === 0) return { better };
  if (kind === 'days_late') {
    const diff = Math.round((now - old) * 10) / 10;
    return { delta: (diff < 0 ? MINUS : '+') + String(Math.abs(diff)), better };
  }
  if (old === 0) return { better };
  const pct = Math.round(((now - old) / old) * 100);
  const sign = pct < 0 ? MINUS : pct > 0 ? '+' : '';
  return { delta: `${sign}${Math.abs(pct)}%`, better };
}

export function compareLabel(old: number): string {
  return 'Old way ' + old.toLocaleString('en-IN');
}