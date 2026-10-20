// The only way screens get data. Phase 3 points the same hooks at the real API.
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import {
  addEvent, confirmRoad, copilot, decideApproval, forecastOverride, getApprovals, getAuditorFlags, getDepartments,
  getEvalsSummary, getEvidence, getHealth, getLedger, getNegotiation, getNoDig, getPlan, getPlanDiff, getPlanMetrics,
  getPlans, getRiskWindows, getRun, getSegments, getVerification, getWork, getWorks, explain, orchestrate,
  reportEmergency, uploadEvidence, verifyLedger, verifyWork, whatIf,
} from './endpoints';
import type {
  Approval, ConfirmBody, CopilotBody, DecideBody, EmergencyInput, EventBody, EvidenceInput, ForecastOverrideBody, Plan,
  RunResult, WhatIfBody,
} from './types';

// Every key starts with the name that live events and mutations invalidate.
export const keys = {
  health: ['health'] as const,
  departments: ['departments'] as const,
  segments: ['segments'] as const,
  works: (planId?: string) => ['works', 'list', planId ?? 'shown'] as const,
  work: (workId: string) => ['works', 'one', workId] as const,
  explain: (entity: string) => ['works', 'explain', entity] as const,
  plans: ['plans'] as const,
  plan: (planId: string) => ['plans', 'one', planId] as const,
  diff: (planId: string, against: string) => ['plans', 'diff', planId, against] as const,
  run: (runId: string) => ['plans', 'run', runId] as const,
  metrics: (planId: string) => ['metrics', planId] as const,
  shownRun: ['shownRun'] as const,
  negotiation: (runId?: string) => ['negotiation', runId ?? 'latest'] as const,
  risk: ['risk'] as const,
  approvals: (status?: Approval['status']) => ['approvals', status ?? 'all'] as const,
  ledger: (limit: number) => ['ledger', limit] as const,
  noDig: ['noDig'] as const,
  flags: ['flags'] as const,
  evidence: (workId: string) => ['evidence', workId] as const,
  verification: (workId: string) => ['verification', workId] as const,
  evals: ['evals'] as const,
};

export function invalidate(qc: QueryClient, ...roots: string[]): Promise<unknown> {
  return Promise.all(roots.map((root) => qc.invalidateQueries({ queryKey: [root] })));
}

// The shown run is the one with the highest number. Ids without a number never take its place.
const runNumber = (id: string): number | null => {
  const found = /^RUN-(\d+)$/.exec(id);
  return found ? Number(found[1]) : null;
};

export function noteRun(qc: QueryClient, runId: string | null | undefined): void {
  if (!runId) return;
  const next = runNumber(runId);
  if (next === null) return;
  const current = qc.getQueryData<string | null>(keys.shownRun);
  const now = current ? runNumber(current) : null;
  if (now !== null && now >= next) return;
  qc.setQueryData<string | null>(keys.shownRun, runId);
}

// ---------- picking a plan ----------
const newestFirst = (plans: Plan[]): Plan[] =>
  plans.filter((p) => p.variant !== 'whatif').sort((a, b) => b.created_at.localeCompare(a.created_at));

function pickActive(plans: Plan[]): Plan | undefined {
  const list = newestFirst([...plans]);
  return list.find((p) => p.status === 'approved')
    ?? list.find((p) => p.status === 'waiting_approval')
    ?? list.find((p) => p.variant === 'naive');
}

const pickOldWay = (plans: Plan[]): Plan | undefined => newestFirst([...plans]).find((p) => p.variant === 'naive');

const pickShown = (plans: Plan[]): Plan | undefined =>
  newestFirst([...plans]).find((p) => p.status === 'waiting_approval') ?? pickActive(plans);

// ---------- queries ----------
export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: getHealth });

export const useDepartments = () => useQuery({ queryKey: keys.departments, queryFn: getDepartments });

export const useSegments = () => useQuery({ queryKey: keys.segments, queryFn: () => getSegments() });

export const useWorks = (planId?: string) => useQuery({ queryKey: keys.works(planId), queryFn: () => getWorks(planId) });

export const useWork = (workId?: string) => useQuery({
  queryKey: keys.work(workId ?? ''), queryFn: () => getWork(workId as string), enabled: Boolean(workId),
});

export const usePlans = () => useQuery({ queryKey: keys.plans, queryFn: getPlans });

export const useActivePlan = () => useQuery({ queryKey: keys.plans, queryFn: getPlans, select: pickActive });

export const useOldWayPlan = () => useQuery({ queryKey: keys.plans, queryFn: getPlans, select: pickOldWay });

export const useShownPlan = () => useQuery({ queryKey: keys.plans, queryFn: getPlans, select: pickShown });

export const usePlan = (planId?: string) => useQuery({
  queryKey: keys.plan(planId ?? ''), queryFn: () => getPlan(planId as string), enabled: Boolean(planId),
});

export const usePlanMetrics = (planId?: string) => useQuery({
  queryKey: keys.metrics(planId ?? ''), queryFn: () => getPlanMetrics(planId as string), enabled: Boolean(planId),
});

export const usePlanDiff = (planId?: string, against = 'naive') => useQuery({
  queryKey: keys.diff(planId ?? '', against), queryFn: () => getPlanDiff(planId as string, against), enabled: Boolean(planId),
});

export const useRun = (runId?: string) => useQuery({
  queryKey: keys.run(runId ?? ''), queryFn: () => getRun(runId as string), enabled: Boolean(runId),
});

export function useShownRunId(): string | undefined {
  const qc = useQueryClient();
  const query = useQuery<string | null>({
    queryKey: keys.shownRun,
    queryFn: () => qc.getQueryData<string | null>(keys.shownRun) ?? null,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  return query.data ?? undefined;
}

// With no run given, this is the run on screen: the newest one anyone has told us about.
export function useNegotiation(runId?: string) {
  const qc = useQueryClient();
  const shown = useShownRunId();
  const id = runId ?? shown;
  return useQuery({
    queryKey: keys.negotiation(id),
    queryFn: async () => {
      const list = await getNegotiation(id);
      noteRun(qc, list[list.length - 1]?.run_id);
      return list;
    },
    placeholderData: runId ? undefined : (previous) => previous,
  });
}

export const useRiskWindows = () => useQuery({ queryKey: keys.risk, queryFn: getRiskWindows });

export const useApprovals = (status?: Approval['status']) => useQuery({
  queryKey: keys.approvals(status), queryFn: () => getApprovals(status),
});

export const useLedger = (limit = 50) => useQuery({ queryKey: keys.ledger(limit), queryFn: () => getLedger({ limit }) });

export const useNoDig = () => useQuery({ queryKey: keys.noDig, queryFn: getNoDig });

export const useAuditorFlags = () => useQuery({ queryKey: keys.flags, queryFn: getAuditorFlags });

export const useEvidence = (workId?: string) => useQuery({
  queryKey: keys.evidence(workId ?? ''), queryFn: () => getEvidence(workId as string), enabled: Boolean(workId),
});

export const useVerification = (workId?: string) => useQuery({
  queryKey: keys.verification(workId ?? ''), queryFn: () => getVerification(workId as string), enabled: Boolean(workId),
});

export const useExplain = (entity?: string) => useQuery({
  queryKey: keys.explain(entity ?? ''), queryFn: () => explain(entity as string), enabled: Boolean(entity),
});

export const useEvalsSummary = () => useQuery({ queryKey: keys.evals, queryFn: getEvalsSummary });

// ---------- mutations ----------
export function useOrchestrate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => orchestrate(),
    onSuccess: (result: RunResult) => {
      noteRun(qc, result.run_id);
      return invalidate(qc, 'plans', 'works', 'approvals', 'negotiation');
    },
  });
}

export function useForecastOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ForecastOverrideBody) => forecastOverride(body),
    onSuccess: (result: RunResult) => {
      noteRun(qc, result.run_id);
      return invalidate(qc, 'risk', 'plans', 'works', 'approvals', 'negotiation');
    },
  });
}

export function useAddEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EventBody) => addEvent(body),
    onSuccess: () => invalidate(qc, 'risk'),
  });
}

export function useDecideApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalId, decision, by, reason }: DecideBody & { approvalId: string }) =>
      decideApproval(approvalId, { decision, by, reason }),
    onSuccess: (result: RunResult) => {
      noteRun(qc, result?.run_id);
      return invalidate(qc, 'approvals', 'plans', 'works', 'metrics', 'ledger');
    },
    // A refused decision (for example "already decided") leaves the list out of date.
    onError: () => invalidate(qc, 'approvals'),
  });
}

export function useVerifyLedger() {
  return useMutation({ mutationFn: () => verifyLedger() });
}

export function useUploadEvidence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, ...input }: EvidenceInput & { workId: string }) => uploadEvidence(workId, input),
    onSuccess: () => invalidate(qc, 'evidence', 'ledger'),
  });
}

export function useVerifyWork() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (workId: string) => verifyWork(workId),
    onSuccess: () => invalidate(qc, 'verification', 'works', 'ledger'),
  });
}

export function useConfirmRoad() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ConfirmBody) => confirmRoad(body),
    onSuccess: () => invalidate(qc, 'works', 'ledger'),
  });
}

export function useReportEmergency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: EmergencyInput) => reportEmergency(input),
    onSuccess: () => invalidate(qc, 'works', 'plans', 'metrics', 'ledger'),
  });
}

export function useWhatIf() {
  return useMutation({ mutationFn: (body: WhatIfBody) => whatIf(body) });
}

export function useCopilot() {
  return useMutation({ mutationFn: (body: CopilotBody) => copilot(body) });
}