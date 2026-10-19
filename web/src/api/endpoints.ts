// One function per endpoint in contracts/api.md. Mock mode answers from mocks/server.ts.
import * as mock from '../mocks/server';
import { ApiError, request, USE_MOCKS } from './client';
import type {
  Approval, AuditorFlag, CitizenReport, ConfirmBody, CopilotBody, CopilotReply, DecideBody, Department,
  EmergencyInput, EvalSummary, EventBody, Evidence, EvidenceInput, Explanation, ForecastOverrideBody, Health,
  LedgerEntry, LedgerOpts, LedgerVerify, Metrics, NegotiationMessage, NoDigEntry, Plan, RiskWindow, RunResult,
  ScenarioLoad, SegmentCollection, Verification, WhatIfBody, WhatIfResult, Work, WorkChange, WorkView,
} from './types';

type Query = Record<string, string | number | undefined>;

function query(params: Query): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

const id = encodeURIComponent;

export function getHealth(): Promise<Health> {
  return USE_MOCKS ? mock.getHealth() : request<Health>('GET', '/health');
}

export function loadScenario(seed: number): Promise<ScenarioLoad> {
  return USE_MOCKS ? mock.loadScenario(seed) : request<ScenarioLoad>('POST', `/scenario/load${query({ seed })}`);
}

export function getSegments(bbox?: string): Promise<SegmentCollection> {
  return USE_MOCKS ? mock.getSegments(bbox) : request<SegmentCollection>('GET', `/segments${query({ bbox })}`);
}

export function getDepartments(): Promise<Department[]> {
  return USE_MOCKS ? mock.getDepartments() : request<Department[]>('GET', '/departments');
}

export function getWorks(planId?: string): Promise<WorkView[]> {
  return USE_MOCKS ? mock.getWorks(planId) : request<WorkView[]>('GET', `/works${query({ plan_id: planId })}`);
}

export function getWork(workId: string): Promise<WorkView> {
  return USE_MOCKS ? mock.getWork(workId) : request<WorkView>('GET', `/works/${id(workId)}`);
}

export function addWork(work: Work): Promise<Work> {
  return USE_MOCKS ? mock.addWork(work) : request<Work>('POST', '/works', work);
}

export function planNaive(): Promise<Plan> {
  return USE_MOCKS ? mock.planNaive() : request<Plan>('POST', '/plan/naive');
}

export function planSolverOnly(): Promise<Plan> {
  return USE_MOCKS ? mock.planSolverOnly() : request<Plan>('POST', '/plan/solver-only');
}

export function orchestrate(): Promise<RunResult> {
  return USE_MOCKS ? mock.orchestrate() : request<RunResult>('POST', '/plan/orchestrate');
}

export function getPlans(): Promise<Plan[]> {
  return USE_MOCKS ? mock.getPlans() : request<Plan[]>('GET', '/plans');
}

export function getPlan(planId: string): Promise<Plan> {
  return USE_MOCKS ? mock.getPlan(planId) : request<Plan>('GET', `/plan/${id(planId)}`);
}

export function getPlanMetrics(planId: string): Promise<Metrics> {
  return USE_MOCKS ? mock.getPlanMetrics(planId) : request<Metrics>('GET', `/plan/${id(planId)}/metrics`);
}

export function getPlanDiff(planId: string, against = 'naive'): Promise<WorkChange[]> {
  return USE_MOCKS
    ? mock.getPlanDiff(planId, against)
    : request<WorkChange[]>('GET', `/plan/${id(planId)}/diff${query({ against })}`);
}

export function getRun(runId: string): Promise<RunResult> {
  return USE_MOCKS ? mock.getRun(runId) : request<RunResult>('GET', `/runs/${id(runId)}`);
}

export function getNegotiation(runId?: string): Promise<NegotiationMessage[]> {
  return USE_MOCKS
    ? mock.getNegotiation(runId)
    : request<NegotiationMessage[]>('GET', `/negotiation${query({ run_id: runId })}`);
}

export function getRiskWindows(): Promise<RiskWindow[]> {
  return USE_MOCKS ? mock.getRiskWindows() : request<RiskWindow[]>('GET', '/risk/windows');
}

export function forecastOverride(body: ForecastOverrideBody): Promise<RunResult> {
  return USE_MOCKS ? mock.forecastOverride(body) : request<RunResult>('POST', '/risk/forecast-override', body);
}

export function addEvent(body: EventBody): Promise<RiskWindow> {
  return USE_MOCKS ? mock.addEvent(body) : request<RiskWindow>('POST', '/events', body);
}

export function getApprovals(status?: Approval['status']): Promise<Approval[]> {
  return USE_MOCKS ? mock.getApprovals(status) : request<Approval[]>('GET', `/approvals${query({ status })}`);
}

export function decideApproval(approvalId: string, body: DecideBody): Promise<RunResult> {
  return USE_MOCKS ? mock.decideApproval(approvalId, body) : request<RunResult>('POST', `/approvals/${id(approvalId)}`, body);
}

export function getLedger(opts: LedgerOpts = {}): Promise<LedgerEntry[]> {
  return USE_MOCKS
    ? mock.getLedger(opts)
    : request<LedgerEntry[]>('GET', `/ledger${query({ limit: opts.limit, before_seq: opts.beforeSeq })}`);
}

export function verifyLedger(): Promise<LedgerVerify> {
  return USE_MOCKS ? mock.verifyLedger() : request<LedgerVerify>('GET', '/ledger/verify');
}

export function uploadEvidence(workId: string, input: EvidenceInput): Promise<Evidence> {
  if (USE_MOCKS) return mock.uploadEvidence(workId, input);
  const form = new FormData();
  form.append('kind', input.kind);
  form.append('photo', input.photo);
  if (input.lat !== undefined) form.append('lat', String(input.lat));
  if (input.lon !== undefined) form.append('lon', String(input.lon));
  if (input.takenAt !== undefined) form.append('taken_at', input.takenAt);
  return request<Evidence>('POST', `/works/${id(workId)}/evidence`, form);
}

export function getEvidence(workId: string): Promise<Evidence[]> {
  return USE_MOCKS ? mock.getEvidence(workId) : request<Evidence[]>('GET', `/works/${id(workId)}/evidence`);
}

export function verifyWork(workId: string): Promise<Verification> {
  return USE_MOCKS ? mock.verifyWork(workId) : request<Verification>('POST', `/works/${id(workId)}/verify`);
}

export async function getVerification(workId: string): Promise<Verification | null> {
  if (USE_MOCKS) return mock.getVerification(workId);
  try {
    return await request<Verification>('GET', `/works/${id(workId)}/verification`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function confirmRoad(body: ConfirmBody): Promise<CitizenReport> {
  return USE_MOCKS ? mock.confirmRoad(body) : request<CitizenReport>('POST', '/reports/confirmation', body);
}

export function getNoDig(): Promise<NoDigEntry[]> {
  return USE_MOCKS ? mock.getNoDig() : request<NoDigEntry[]>('GET', '/no-dig');
}

export function reportEmergency(input: EmergencyInput): Promise<CitizenReport> {
  if (USE_MOCKS) return mock.reportEmergency(input);
  const form = new FormData();
  form.append('category', input.category);
  form.append('lat', String(input.lat));
  form.append('lon', String(input.lon));
  if (input.note !== undefined) form.append('note', input.note);
  if (input.photo !== undefined) form.append('photo', input.photo);
  return request<CitizenReport>('POST', '/reports/emergency', form);
}

export function getAuditorFlags(): Promise<AuditorFlag[]> {
  return USE_MOCKS ? mock.getAuditorFlags() : request<AuditorFlag[]>('GET', '/auditor/flags');
}

export function explain(entity: string): Promise<Explanation> {
  return USE_MOCKS ? mock.explain(entity) : request<Explanation>('GET', `/explain/${id(entity)}`);
}

export function whatIf(body: WhatIfBody): Promise<WhatIfResult> {
  return USE_MOCKS ? mock.whatIf(body) : request<WhatIfResult>('POST', '/plan/whatif', body);
}

export function copilot(body: CopilotBody): Promise<CopilotReply> {
  return USE_MOCKS ? mock.copilot(body) : request<CopilotReply>('POST', '/copilot', body);
}

export function getEvalsSummary(): Promise<EvalSummary> {
  return USE_MOCKS ? mock.getEvalsSummary() : request<EvalSummary>('GET', '/evals/summary');
}