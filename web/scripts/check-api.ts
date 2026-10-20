// Run with: node --experimental-strip-types scripts/check-api.ts [--base http://localhost:8000] [--ws ws://localhost:8000/ws]
// Reads from the API and prints one line per check. It never sends a POST.
import type {
  Approval, AuditorFlag, Department, EvalSummary, Explanation, Health, LedgerEntry, Metrics, NegotiationMessage, Plan,
  RiskWindow, RunResult, SegmentCollection, WorkChange, WorkView,
} from '../src/api/types.ts';

function option(name: string, fallback: string): string {
  const at = process.argv.indexOf(name);
  return at >= 0 && process.argv[at + 1] ? process.argv[at + 1] : fallback;
}

const BASE = option('--base', 'http://localhost:8000').replace(/\/$/, '');
const WS = option('--ws', BASE.replace(/^http/, 'ws') + '/ws');

let failed = 0;
function say(kind: 'PASS' | 'FAIL' | 'SKIP', what: string, text: string): void {
  if (kind === 'FAIL') failed += 1;
  console.log(`${kind} ${what} - ${text}`);
}

interface Answer<T> {
  status: number;
  body: T | null;
  problem?: string;
}

async function get<T>(path: string): Promise<Answer<T>> {
  try {
    const response = await fetch(BASE + path, { signal: AbortSignal.timeout(10000) });
    let body: T | null = null;
    try {
      body = (await response.json()) as T;
    } catch {
      body = null;
    }
    return { status: response.status, body };
  } catch (error) {
    const name = error instanceof Error ? error.name : 'error';
    return { status: 0, body: null, problem: name === 'TimeoutError' ? 'no answer within 10 s' : 'could not reach ' + BASE };
  }
}

// Runs one check. A thrown error becomes a FAIL line.
async function check(what: string, run: () => Promise<void>): Promise<void> {
  try {
    await run();
  } catch (error) {
    say('FAIL', what, error instanceof Error ? error.message : 'unexpected error');
  }
}

function need<T>(answer: Answer<T>, what: string): T {
  if (answer.status === 0) throw new Error(answer.problem ?? 'no answer');
  if (answer.status !== 200 || answer.body === null) throw new Error(`${what} answered ${answer.status}`);
  return answer.body;
}

const isNumber = (x: unknown): boolean => typeof x === 'number' && Number.isFinite(x);

// The active plan: newest approved, else newest waiting, else the old way.
function pickActive(plans: Plan[]): Plan | undefined {
  const list = plans.filter((p) => p.variant !== 'whatif').sort((a, b) => b.created_at.localeCompare(a.created_at));
  return list.find((p) => p.status === 'approved') ?? list.find((p) => p.status === 'waiting_approval')
    ?? list.find((p) => p.variant === 'naive');
}

let segmentIds = new Set<string>();
let plans: Plan[] = [];
let active: Plan | undefined;
let works: WorkView[] = [];

await check('GET /health', async () => {
  const h = need(await get<Health>('/health'), '/health');
  if (h.ok !== true || h.db !== true) throw new Error(`ok is ${h.ok} and db is ${h.db}`);
  if (h.weather_mode !== 'fixture' && h.weather_mode !== 'live') throw new Error(`weather_mode is ${h.weather_mode}`);
  say('PASS', 'GET /health', `weather ${h.weather_mode}`);
});

await check('GET /segments', async () => {
  const c = need(await get<SegmentCollection>('/segments'), '/segments');
  if (c.type !== 'FeatureCollection' || c.features.length === 0) throw new Error('not a FeatureCollection with features');
  const keys = ['segment_id', 'name', 'road_class', 'low_lying', 'protected_until'];
  for (const f of c.features) {
    if (f.geometry?.type !== 'LineString') throw new Error('a feature is not a LineString');
    const missing = keys.filter((k) => !(k in (f.properties ?? {})));
    if (missing.length) throw new Error(`a feature lacks ${missing.join(', ')}`);
  }
  segmentIds = new Set(c.features.map((f) => String(f.properties.segment_id)));
  say('PASS', 'GET /segments', `${c.features.length} segments`);
});

await check('GET /departments', async () => {
  const d = need(await get<Department[]>('/departments'), '/departments');
  const ids = d.map((x) => x.id).sort().join(',');
  const want = ['water', 'drainage', 'gas', 'power', 'telecom', 'roads'].sort().join(',');
  if (ids !== want) throw new Error(`got ${ids}`);
  say('PASS', 'GET /departments', 'six departments');
});

await check('GET /plans', async () => {
  plans = need(await get<Plan[]>('/plans'), '/plans');
  if (plans.length === 0) throw new Error('no plans');
  if (!plans.some((p) => p.variant === 'naive')) throw new Error('no old-way plan');
  active = pickActive(plans);
  say('PASS', 'GET /plans', `${plans.length} plans, active ${active?.plan_id ?? 'none'}`);
});

await check('GET /works', async () => {
  works = need(await get<WorkView[]>('/works'), '/works');
  const missing: string[] = [];
  for (const v of works) for (const id of v.work.segment_ids) if (!segmentIds.has(id) && !missing.includes(id)) missing.push(id);
  if (missing.length) throw new Error(`segments not in /segments: ${missing.slice(0, 3).join(', ')}`);
  say('PASS', 'GET /works', `${works.length} works`);
});

await check('GET /works/<id>', async () => {
  const first = works[0]?.work.work_id;
  if (!first) {
    say('SKIP', 'GET /works/<id>', 'no works');
    return;
  }
  const v = need(await get<WorkView>('/works/' + encodeURIComponent(first)), '/works/' + first);
  if (v.work.work_id !== first) throw new Error(`asked for ${first}, got ${v.work.work_id}`);
  say('PASS', `GET /works/${first}`, v.status);
});

await check('GET /plan/<active>/metrics', async () => {
  if (!active) throw new Error('no active plan');
  const id = encodeURIComponent(active.plan_id);
  const m = need(await get<Metrics>(`/plan/${id}/metrics`), 'metrics') as unknown as Record<string, unknown>;
  const bad = Object.keys(m).filter((k) => k !== 'plan_id' && !isNumber(m[k]));
  if (bad.length) throw new Error(`not numbers: ${bad.join(', ')}`);
  const d = need(await get<WorkChange[]>(`/plan/${id}/diff?against=naive`), 'diff');
  if (!Array.isArray(d)) throw new Error('diff is not an array');
  say('PASS', 'GET /plan/<active>/metrics and diff', `${Object.keys(m).length - 1} numbers, ${d.length} changes`);
});

await check('GET /negotiation', async () => {
  const list = need(await get<NegotiationMessage[]>('/negotiation'), '/negotiation');
  if (!Array.isArray(list)) throw new Error('not an array');
  if (list.length === 0) {
    say('SKIP', 'GET /negotiation', 'no run yet');
    return;
  }
  const runId = list[list.length - 1].run_id;
  const run = need(await get<RunResult>('/runs/' + encodeURIComponent(runId)), '/runs/' + runId);
  say('PASS', 'GET /negotiation and /runs', `${list.length} messages, ${runId} is ${run.status}`);
});

await check('GET /risk/windows', async () => {
  const list = need(await get<RiskWindow[]>('/risk/windows'), '/risk/windows');
  const sources = ['open-meteo', 'fixture', 'override', 'event'];
  for (const w of list) {
    if (!['rain', 'air', 'event'].includes(w.kind)) throw new Error(`${w.window_id} has kind ${w.kind}`);
    if (!sources.includes(w.source)) throw new Error(`${w.window_id} has source ${w.source}`);
    if (w.start_day > w.end_day) throw new Error(`${w.window_id} ends before it starts`);
  }
  say('PASS', 'GET /risk/windows', `${list.length} windows`);
});

await check('GET /approvals', async () => {
  const all = need(await get<Approval[]>('/approvals'), '/approvals');
  const pending = need(await get<Approval[]>('/approvals?status=pending'), '/approvals?status=pending');
  say('PASS', 'GET /approvals', `${all.length} in all, ${pending.length} pending`);
});

await check('GET /ledger', async () => {
  const list = need(await get<LedgerEntry[]>('/ledger?limit=5'), '/ledger');
  for (let i = 1; i < list.length; i += 1) if (list[i].seq >= list[i - 1].seq) throw new Error('seq does not go down');
  say('PASS', 'GET /ledger', `${list.length} entries, newest ${list[0]?.seq ?? 'none'}`);
});

await check('GET /explain', async () => {
  const targets = [works[0]?.work.work_id, active?.plan_id].filter((x): x is string => Boolean(x));
  const seen: string[] = [];
  for (const id of targets) {
    const answer = await get<Explanation>('/explain/' + encodeURIComponent(id));
    if (answer.status === 404) {
      say('SKIP', `GET /explain/${id}`, 'not on this server yet');
      continue;
    }
    const e = need(answer, '/explain/' + id);
    if (!Array.isArray(e.reasons) || !Array.isArray(e.rules)) throw new Error(`${id}: reasons and rules must be arrays`);
    seen.push(id);
  }
  if (seen.length) say('PASS', 'GET /explain', seen.join(', '));
});

await check('GET /evals/summary and /auditor/flags', async () => {
  for (const path of ['/evals/summary', '/auditor/flags']) {
    const answer = await get<EvalSummary | AuditorFlag[]>(path);
    if (answer.status === 404) {
      say('SKIP', `GET ${path}`, 'not on this server yet');
      continue;
    }
    need(answer, path);
    say('PASS', `GET ${path}`, 'answers');
  }
});

await check('WebSocket', async () => {
  if (typeof WebSocket === 'undefined') {
    say('SKIP', 'WebSocket', 'this Node has no WebSocket');
    return;
  }
  await new Promise<void>((resolve, reject) => {
    const socket = new WebSocket(WS);
    const timer = setTimeout(() => {
      socket.close();
      reject(new Error('did not open within 3 s'));
    }, 3000);
    socket.onopen = () => {
      clearTimeout(timer);
      socket.close();
      resolve();
    };
    socket.onerror = () => {
      clearTimeout(timer);
      reject(new Error('could not open ' + WS));
    };
  });
  say('PASS', 'WebSocket', 'opens');
});

process.exit(failed > 0 ? 1 : 0);
