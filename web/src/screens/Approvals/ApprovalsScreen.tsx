import { useState } from 'react';
import type { ReactNode } from 'react';
import { useApprovals, useDecideApproval, useOldWayPlan, usePlanDiff, usePlanMetrics } from '../../api/hooks';
import { compareLabel, dayRange, inr, metricDelta, shortTime, signedInr } from '../../api/format';
import type { Approval, Tier } from '../../api/types';
import { useRole } from '../../app/role';
import { Banner, Button, Card, DiffRow, Icon, MetricTile, PhoneScreen, StatusBadge, StepList, TextField } from '../../ui';

type Decision = 'approve' | 'reject';

const TIERS: Record<Exclude<Tier, 'auto'>, { who: string; label: string; detail: string }> = {
  ward_engineer: { who: 'the ward engineer', label: 'Ward engineer', detail: 'Plans that change 5 or more works' },
  department_officer: { who: 'the department officer', label: 'Department officer', detail: 'Plans that change up to 4 works of one department' },
  commissioner: { who: 'the commissioner', label: 'Commissioner', detail: 'Plans that change more than 50 works or cost more than ₹10,00,000' },
};

const COLUMN = { display: 'flex', flexDirection: 'column', gap: 8 } as const;
const ROW = { display: 'flex', justifyContent: 'space-between', gap: 8 } as const;
const SAND = { background: 'var(--sand)', borderRadius: 'var(--radius-xl)' } as const;

const newest = (list: Approval[] = []): Approval | undefined =>
  [...list].sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];

export default function ApprovalsScreen() {
  const { role } = useRole();
  const approvals = useApprovals('pending');
  const decide = useDecideApproval();
  // The decided approval leaves the pending list, so it is kept here to go on showing it.
  const [decided, setDecided] = useState<{ approval: Approval; decision: Decision } | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  const approval = decided?.approval ?? newest(approvals.data);
  const diff = usePlanDiff(approval?.plan_id, 'naive');
  const metrics = usePlanMetrics(approval?.plan_id);
  const oldWay = useOldWayPlan();
  const oldMetrics = usePlanMetrics(oldWay.data?.plan_id);

  const loading = approvals.isLoading || diff.isLoading || metrics.isLoading || oldWay.isLoading || oldMetrics.isLoading;
  const badge = decided?.decision === 'approve'
    ? <StatusBadge status="approved">Approved</StatusBadge>
    : decided?.decision === 'reject'
      ? <StatusBadge status="fail">Rejected</StatusBadge>
      : <StatusBadge status="pending">Waiting</StatusBadge>;

  if (loading || !approval) {
    return (
      <PhoneScreen title="Approval" backTo="/" badge={badge}>
        {loading ? (
          <>
            <div style={{ ...SAND, height: 96 }} />
            <div style={{ ...SAND, height: 240 }} />
          </>
        ) : (
          <Card soft style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 12 }}>
            <Icon name="handshake" size={24} />
            <p className="body-l" style={{ margin: 0 }}>Nothing is waiting for you.</p>
            <Button as="a" href="/command">Open command centre</Button>
          </Card>
        )}
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

  async function send(decision: Decision) {
    if (!approval) return;
    const by = role === 'department_officer' ? 'department_officer' : 'ward_engineer';
    try {
      await decide.mutateAsync({ approvalId: approval.approval_id, decision, by, reason: decision === 'reject' ? reason.trim() : undefined });
      setDecided({ approval, decision });
    } catch {
      // The danger banner below shows the failure; the buttons stay so the user can try again.
    }
  }

  const reasonReady = reason.trim().length >= 3;
  let footer: ReactNode;
  if (decided) {
    footer = <Button as="a" href="/command" block>Open command centre</Button>;
  } else if (rejecting) {
    footer = (
      <>
        {reasonReady ? null : <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>Write a reason first.</p>}
        <Button variant="danger" block disabled={!reasonReady || decide.isPending} onClick={() => send('reject')}>Reject plan</Button>
        <Button block onClick={() => { setRejecting(false); setReason(''); }}>Cancel</Button>
      </>
    );
  } else {
    footer = (
      <>
        <Button variant="danger" icon="x" block disabled={decide.isPending} onClick={() => setRejecting(true)}>Reject</Button>
        <Button variant="primary" block disabled={decide.isPending} onClick={() => send('approve')}>Approve plan</Button>
      </>
    );
  }

  return (
    <PhoneScreen title="Approval" backTo="/" badge={badge} footer={footer}>
      {decided?.decision === 'approve' ? (
        <Banner tone="ok" title="Plan approved">It is in the public record. Department heads are told.</Banner>
      ) : decided?.decision === 'reject' ? (
        <Banner tone="info" title="Plan rejected">The scheduler will make a new plan with your reason.</Banner>
      ) : decide.isError ? (
        <Banner tone="danger" title="Could not send">Check your connection and try again.</Banner>
      ) : null}

      <Card style={COLUMN}>
        <h2 className="title-l" style={{ margin: 0 }}>{approval.summary}</h2>
        <p className="body-l" style={{ margin: 0, color: 'var(--ink-2)' }}>
          {`Made by the scheduler at ${shortTime(approval.requested_at)}. `}
          {tier ? `It needs you, ${tier.who}, because it changes ${changes.length} works.` : 'It needs no approval.'}
        </p>
      </Card>

      {now && old ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
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
        <div style={ROW}><span className="body">Repeat repairs avoided</span><span className="mono">{inr(-avoided)}</span></div>
      </Card>

      <section style={COLUMN}>
        <h2 className="title" style={{ margin: 0 }}>Rules check</h2>
        <StepList
          steps={[
            { text: 'Rules check passed', detail: 'No protected road is dug; every deposit is held', status: 'done' },
            { text: `${needs.label}: you`, detail: needs.detail, status: decided ? 'done' : 'needs' },
            { text: 'Department heads are told', detail: 'After you approve', status: decided?.decision === 'approve' ? 'done' : 'waiting' },
          ]}
        />
      </section>

      {rejecting && !decided ? (
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
