import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { USE_MOCKS } from '../../api/client';
import {
  useApprovals, useDecideApproval, useExplain, useOldWayPlan, usePlan, usePlanDiff, usePlanMetrics,
} from '../../api/hooks';
import { actorLabel, compareLabel, dayRange, inr, metricDelta, shortTime, signedInr } from '../../api/format';
import type { Approval, RuleCheck, Tier } from '../../api/types';
import { useRole } from '../../app/role';
import {
  Banner, Button, Card, DiffRow, EmptyState, FocusTarget, isMissing, LoadError, MetricTile, PhoneScreen, problemText, Skeleton,
  StatusBadge, StepList, TextField,
} from '../../ui';
import type { StepListProps } from '../../ui';

type Decision = 'approve' | 'reject';
type Step = StepListProps['steps'][number];

const TIERS: Record<Exclude<Tier, 'auto'>, { who: string; label: string; detail: string }> = {
  ward_engineer: { who: 'the ward engineer', label: 'Ward engineer', detail: 'Plans that change 5 or more works' },
  department_officer: { who: 'the department officer', label: 'Department officer', detail: 'Plans that change up to 4 works of one department' },
  commissioner: { who: 'the commissioner', label: 'Commissioner', detail: 'Plans that change more than 50 works or cost more than ₹10,00,000' },
};

const COLUMN = { display: 'flex', flexDirection: 'column', gap: 8 } as const;
const ROW = { display: 'flex', justifyContent: 'space-between', gap: 8 } as const;
const FIXED_RULES: Step = { text: 'Rules check passed', detail: 'No protected road is dug; every deposit is held', status: 'done' };
const LOADING_RULES: Step = { text: 'Rules check', detail: 'Loading the results', status: 'waiting' };

// The backend's approval summary counts the same way: "1 work changes".
const worksText = (n: number) => (n === 1 ? '1 work' : `${n} works`);

const newest = (list: Approval[] = []): Approval | undefined =>
  [...list].sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];

function ruleSteps(rules: RuleCheck[]): Step[] {
  const flagged = rules.filter((r) => r.severity !== 'ok');
  if (flagged.length === 0) {
    return [{ text: 'Rules check passed', detail: rules.map((r) => r.detail).join('; ') || undefined, status: 'done' }];
  }
  return flagged.map((r) => (r.severity === 'fail'
    ? { text: 'Rules check failed', detail: r.detail, status: 'needs' }
    : { text: r.detail, status: 'needs' }));
}

export default function ApprovalsScreen() {
  const { role } = useRole();
  const pending = useApprovals('pending');
  const all = useApprovals();
  const decide = useDecideApproval();
  // The decided approval leaves the pending list, so it is kept here to go on showing it.
  const [decided, setDecided] = useState<{ approval: Approval; decision: Decision } | null>(null);
  // The approval on screen stays on screen when another screen decides it.
  const [shownId, setShownId] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  const latestCopy = all.data?.find((a) => a.approval_id === shownId);
  const approval = decided?.approval ?? latestCopy ?? pending.data?.find((a) => a.approval_id === shownId) ?? newest(pending.data);
  // A decision from this screen can reach the list before its own reply does; that is not "elsewhere".
  const elsewhere = !decided && !decide.isPending && !decide.isSuccess && latestCopy && latestCopy.status !== 'pending' ? latestCopy : null;
  const waitingNext = decided || elsewhere ? newest(pending.data?.filter((a) => a.approval_id !== approval?.approval_id)) : undefined;

  useEffect(() => {
    if (!shownId && approval) setShownId(approval.approval_id);
  }, [shownId, approval]);

  const plan = usePlan(USE_MOCKS ? undefined : approval?.plan_id);
  // shortcut: mock mode keeps the old-way diff that artboard 06 draws; the real screen lists what this approval changes
  const against = USE_MOCKS ? 'naive' : (plan.data?.base_plan_id ?? 'naive');
  const diff = usePlanDiff(USE_MOCKS || plan.data ? approval?.plan_id : undefined, against);
  const metrics = usePlanMetrics(approval?.plan_id);
  const oldWay = useOldWayPlan();
  const oldMetrics = usePlanMetrics(oldWay.data?.plan_id);
  const explanation = useExplain(approval?.plan_id);

  const loading = pending.isLoading || plan.isLoading || diff.isLoading || metrics.isLoading || oldWay.isLoading || oldMetrics.isLoading;
  const outcome = decided?.decision === 'approve' || elsewhere?.status === 'approved'
    ? 'approved'
    : decided?.decision === 'reject' || elsewhere?.status === 'rejected' ? 'rejected' : null;
  const badge = outcome === 'approved'
    ? <StatusBadge status="approved">Approved</StatusBadge>
    : outcome === 'rejected'
      ? <StatusBadge status="fail">Rejected</StatusBadge>
      : <StatusBadge status="pending">Waiting</StatusBadge>;

  const queries = [pending, all, plan, diff, metrics, oldWay, oldMetrics, explanation].filter((q) => !isMissing(q.error));
  if (loading) {
    return (
      <PhoneScreen title="Approval" backTo="/" badge={badge} busy>
        <Skeleton height={96} />
        <Skeleton height={240} />
      </PhoneScreen>
    );
  }
  if (!approval) {
    return (
      <PhoneScreen title="Approval" backTo="/" badge={badge}>
        {pending.isError
          ? <LoadError queries={queries} />
          : <EmptyState icon="handshake" text="Nothing is waiting for you." action={<Button as="a" href="/command">Open command centre</Button>} />}
      </PhoneScreen>
    );
  }

  const changes = diff.data ?? [];
  const extraCost = changes.reduce((sum, c) => sum + Math.max(0, c.cost_delta_inr), 0);
  const avoided = changes.reduce((sum, c) => sum + Math.min(0, c.cost_delta_inr), 0);
  const tier = approval.tier === 'auto' ? null : TIERS[approval.tier];
  const needs = tier ?? TIERS.ward_engineer;
  const now = metrics.data;
  const old = oldMetrics.data;
  const rules = explanation.data?.rules;
  const rulesFailed = rules?.some((r) => r.severity === 'fail') ?? false;
  const rulesRows = rules ? ruleSteps(rules) : [USE_MOCKS ? FIXED_RULES : LOADING_RULES];
  const problem = decide.isError && !elsewhere ? problemText(decide.error) : null;

  async function send(decision: Decision) {
    if (!approval) return;
    const by = role === 'department_officer' ? 'department_officer' : 'ward_engineer';
    try {
      await decide.mutateAsync({ approvalId: approval.approval_id, decision, by, reason: decision === 'reject' ? reason.trim() : undefined });
      setDecided({ approval, decision });
    } catch (error) {
      // The danger banner shows the failure; the reason stays so the user can try again.
      if (problemText(error).title === 'Already decided') {
        void pending.refetch();
        void all.refetch();
      }
    }
  }

  function showNext(next: Approval) {
    setDecided(null);
    setRejecting(false);
    setReason('');
    decide.reset();
    setShownId(next.approval_id);
  }

  const reasonReady = reason.trim().length >= 3;
  const sending = decide.isPending;
  let footer: ReactNode;
  if (decided) {
    footer = <Button as="a" href="/command" block>Open command centre</Button>;
  } else if (elsewhere) {
    footer = <Button variant="secondary" block as="a" href="/command">Open command centre</Button>;
  } else if (rejecting) {
    footer = (
      <>
        {reasonReady ? null : <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>Write a reason first.</p>}
        <Button variant="danger" block disabled={!reasonReady || sending} onClick={() => void send('reject')}>
          {sending ? 'Sending…' : 'Reject plan'}
        </Button>
        <Button block disabled={sending} onClick={() => { setRejecting(false); setReason(''); }}>Cancel</Button>
      </>
    );
  } else {
    footer = (
      <>
        <Button variant="danger" icon="x" block disabled={sending} onClick={() => setRejecting(true)}>Reject</Button>
        <Button variant="primary" block disabled={sending} onClick={() => void send('approve')}>{sending ? 'Sending…' : 'Approve plan'}</Button>
      </>
    );
  }

  return (
    <PhoneScreen title="Approval" backTo="/" badge={badge} footer={footer}>
      <LoadError queries={queries} />
      {rulesFailed ? <Banner tone="warn" title="The rules check failed">Read why below before you decide.</Banner> : null}
      {/* Always present so the decision is announced; display contents keeps the empty region out of the layout. */}
      <div aria-live="polite" style={{ display: 'contents' }}>
        {decided ? (
          <FocusTarget>
            {decided.decision === 'approve'
              ? <Banner tone="ok" title="Plan approved">It is in the public record. Department heads are told.</Banner>
              : <Banner tone="info" title="Plan rejected">The scheduler will make a new plan with your reason.</Banner>}
          </FocusTarget>
        ) : elsewhere ? (
          <Banner tone="info" title="Decided on another screen">
            {`${actorLabel(elsewhere.decided_by ?? 'system')} ${elsewhere.status} this plan at ${shortTime(elsewhere.decided_at ?? elsewhere.requested_at)}.`}
          </Banner>
        ) : problem ? (
          <Banner tone="danger" title={problem.title}>{problem.text}</Banner>
        ) : null}
        {waitingNext ? (
          <Banner tone="info" title="A new plan is waiting" action={<Button variant="ghost" onClick={() => showNext(waitingNext)}>Show it</Button>} />
        ) : null}
      </div>

      <Card style={COLUMN}>
        <h2 className="title-l" style={{ margin: 0 }}>{approval.summary}</h2>
        <p className="body-l" style={{ margin: 0, color: 'var(--ink-2)' }}>
          {`Made by the scheduler at ${shortTime(approval.requested_at)}. `}
          {tier ? `It needs you, ${tier.who}, because it changes ${worksText(changes.length)}.` : 'It needs no approval.'}
        </p>
      </Card>

      {now && old ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
          <MetricTile
            label="Digs per road"
            value={now.digs_per_road}
            compare={compareLabel(old.digs_per_road)}
            {...metricDelta(now.digs_per_road, old.digs_per_road, 'digs_per_road')}
          />
          <MetricTile
            label="Rain hours"
            value={now.trench_hours_in_rain}
            unit="h"
            compare={compareLabel(old.trench_hours_in_rain)}
            {...metricDelta(now.trench_hours_in_rain, old.trench_hours_in_rain, 'trench_hours_in_rain')}
          />
        </div>
      ) : null}

      <section style={COLUMN}>
        <h2 className="title" style={{ margin: 0 }}>What changes</h2>
        <ul style={{ ...COLUMN, listStyle: 'none', margin: 0, padding: 0 }}>
          {changes.map((c) => (
            <DiffRow
              key={c.work_id}
              dept={c.dept}
              title={c.title}
              was={c.from_start != null && c.from_end != null ? dayRange(c.from_start, c.from_end) : undefined}
              to={dayRange(c.to_start, c.to_end)}
              reason={c.reason}
              cost={signedInr(c.cost_delta_inr)}
              costDir={c.cost_delta_inr < 0 ? 'down' : 'up'}
            />
          ))}
        </ul>
      </section>

      <Card flat style={COLUMN}>
        <h2 className="title" style={{ margin: 0 }}>Money</h2>
        <div style={ROW}><span className="body">Extra cost of moving works</span><span className="mono">{signedInr(extraCost)}</span></div>
        {avoided < 0 ? (
          <div style={ROW}><span className="body">Repeat repairs avoided</span><span className="mono">{inr(-avoided)}</span></div>
        ) : null}
      </Card>

      <section style={COLUMN}>
        <h2 className="title" style={{ margin: 0 }}>Rules check</h2>
        <StepList
          steps={[
            ...rulesRows,
            { text: `${needs.label}: you`, detail: needs.detail, status: outcome ? 'done' : 'needs' },
            { text: 'Department heads are told', detail: 'After you approve', status: outcome === 'approved' ? 'done' : 'waiting' },
          ]}
        />
      </section>

      {rejecting && !decided && !elsewhere ? (
        <TextField
          label="Reason"
          hint="Needed when you reject"
          placeholder="What should change?"
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      ) : null}
    </PhoneScreen>
  );
}
