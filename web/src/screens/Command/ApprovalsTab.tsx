import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { actorLabel, dateTimeLabel, dayRange, errorText, shortTime, signedInr, timeLabel } from '../../api/format';
import { USE_MOCKS } from '../../api/client';
import {
  useApprovals, useDecideApproval, useExplain, useLedger, useNegotiation, useOldWayPlan, usePlan, usePlanDiff, usePlanMetrics,
  useRulesCheck,
} from '../../api/hooks';
import type { Approval, LedgerEntry, Tier } from '../../api/types';
import { Banner, Button, Card, DiffRow, Icon, StatusBadge, StepList, Tag, TextField } from '../../ui';

const TIERS: Record<Tier, { text: string; detail: string }> = {
  ward_engineer: { text: 'Ward engineer: you', detail: 'Plans that change 5 or more works' },
  department_officer: { text: 'Department officer', detail: 'Plans that change up to 4 works of one department' },
  commissioner: { text: 'Commissioner', detail: 'Plans that change more than 50 works or cost over \u20b910,00,000' },
  auto: { text: 'Approved by the rules', detail: 'One work, under \u20b910,000' },
};

interface Decided {
  approval: Approval;
  decision: 'approve' | 'reject';
  reason: string;
}

// "Munchur Road: 4 digs become 2" gives "4 digs \u2192 2 on Munchur Road".
function digsTag(text: string | undefined): string | null {
  const found = text?.match(/(?:Option [A-Z]\.\s*)?(.+?):\s*(\d+) digs become (\d+)/);
  return found ? `${found[2]} digs \u2192 ${found[3]} on ${found[1]}` : null;
}

// What the approval card is called: the summary up to the first " · ".
const cardTitle = (summary: string): string => summary.split(' · ')[0];

const oneDecimal = (n: number): string => (Math.round(n * 10) / 10).toFixed(1);

interface Past {
  key: string;
  at: string;
  title: string;
  badge: 'emergency' | 'approved' | 'fail';
  word: string;
  line: string;
}

// On the real server: every decided approval and every emergency dig, newest first.
function pastItems(approvals: Approval[], emergencies: LedgerEntry[]): Past[] {
  const decided: Past[] = approvals.map((a) => {
    const at = a.decided_at ?? a.requested_at;
    const by = actorLabel(a.decided_by ?? 'system');
    return a.status === 'rejected'
      ? { key: a.approval_id, at, title: cardTitle(a.summary), badge: 'fail', word: 'Rejected', line: `Rejected by ${by} · ${dateTimeLabel(at)}${a.reason ? ': ' + a.reason : ''}` }
      : { key: a.approval_id, at, title: cardTitle(a.summary), badge: 'approved', word: 'Approved', line: `Approved by ${by} · ${dateTimeLabel(at)}` };
  });
  const urgent: Past[] = emergencies.map((e) => ({
    key: `ledger-${e.seq}`, at: e.ts, title: 'Emergency dig', badge: 'emergency', word: 'Emergency', line: `${e.summary} · ${timeLabel(e.ts)}`,
  }));
  return [...decided, ...urgent].sort((a, b) => b.at.localeCompare(a.at));
}

function earlier(a: Approval): { badge: 'emergency' | 'approved' | 'fail'; word: string; line: string } {
  const when = dateTimeLabel(a.decided_at ?? a.requested_at);
  if (a.tier === 'auto') {
    return {
      badge: 'emergency', word: 'Emergency',
      line: `${a.reason ?? a.summary} \u00b7 allowed at once by the rules \u00b7 ${shortTime(a.decided_at ?? a.requested_at)}`,
    };
  }
  const by = a.decided_by === 'ward_engineer' ? 'you' : actorLabel(a.decided_by ?? 'system');
  if (a.status === 'rejected') {
    return { badge: 'fail', word: 'Rejected', line: `Rejected by ${by} \u00b7 ${when}${a.reason ? ': ' + a.reason : ''}` };
  }
  return { badge: 'approved', word: 'Approved', line: `Approved by ${by} \u00b7 ${when}` };
}

export function ApprovalsTab() {
  const all = useApprovals().data ?? [];
  const decide = useDecideApproval();
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | undefined>();
  const [failure, setFailure] = useState<string | undefined>();
  const [done, setDone] = useState<Decided | null>(null);
  const field = useRef<HTMLDivElement>(null);

  const pending = all.filter((a) => a.status === 'pending').sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];
  const current = pending ?? done?.approval;
  const decided = done && current && done.approval.approval_id === current.approval_id ? done : null;

  const plan = usePlan(current?.plan_id).data;
  const changes = usePlanDiff(current?.plan_id, 'naive').data ?? [];
  const run = useNegotiation(current?.run_id).data ?? [];
  const old = useOldWayPlan().data;
  const planMetrics = usePlanMetrics(current?.plan_id).data;
  const oldMetrics = usePlanMetrics(old?.plan_id).data;
  const explained = useExplain(current?.plan_id).data;
  const rulesLine = useRulesCheck(current?.plan_id);
  const ledger = useLedger(200).data ?? [];

  // The road tag needs a decision that names a road; otherwise the average digs per road is shown.
  const road = digsTag(plan?.notes.find((n) => /digs become/.test(n)) ?? run.find((m) => m.type === 'DECISION')?.body);
  const digsOld = oldMetrics?.digs_per_road;
  const digsNow = planMetrics?.digs_per_road;
  const digs = road ?? (digsOld !== undefined && digsNow !== undefined && oldMetrics && planMetrics && oldMetrics.plan_id !== planMetrics.plan_id
    && oneDecimal(digsOld) !== oneDecimal(digsNow) ? `Digs per road ${oneDecimal(digsOld)} → ${oneDecimal(digsNow)}` : null);

  // The first rules step: the explanation when the server has one, else what the rules check wrote down.
  const rule = explained?.rules.find((r) => r.severity !== 'ok') ?? explained?.rules[0];
  const rulesStep = rule
    ? { text: rule.name, detail: rule.detail, status: rule.severity === 'ok' ? ('done' as const) : ('needs' as const) }
    : rulesLine
      ? {
        text: rulesLine,
        detail: rulesLine === 'Rules check passed' ? 'No protected road is dug; every deposit is held' : undefined,
        status: /failed/i.test(rulesLine) ? ('needs' as const) : ('done' as const),
      }
      : { text: 'Rules check', detail: undefined, status: 'waiting' as const };
  const rainOld = oldMetrics?.trench_hours_in_rain ?? 0;
  const rainNow = planMetrics?.trench_hours_in_rain ?? 0;

  const send = (decision: 'approve' | 'reject') => {
    if (!current) return;
    const text = reason.trim();
    if (decision === 'reject' && !text) {
      setError('Give a reason to reject');
      field.current?.querySelector('input')?.focus();
      return;
    }
    setError(undefined);
    setFailure(undefined);
    decide.mutate(
      { approvalId: current.approval_id, decision, by: 'ward_engineer', reason: decision === 'reject' ? text : undefined },
      { onSuccess: () => setDone({ approval: current, decision, reason: text }), onError: (e) => setFailure(errorText(e)) },
    );
  };

  const earlierApprovals = all
    .filter((a) => a.status !== 'pending' && a.approval_id !== current?.approval_id)
    .sort((a, b) => (b.decided_at ?? b.requested_at).localeCompare(a.decided_at ?? a.requested_at));
  // The mock keeps its own story; the real server shows what was decided and every emergency dig.
  const history: Past[] = USE_MOCKS
    ? earlierApprovals.map((a) => ({ key: a.approval_id, at: a.decided_at ?? a.requested_at, title: a.summary, ...earlier(a) }))
    : pastItems(earlierApprovals, ledger.filter((e) => e.action === 'emergency.allowed'));

  const tier = current ? TIERS[current.tier] : null;
  const approved = decided?.decision === 'approve';

  return (
    <div className="mm-app-appr">
      {current && tier ? (
        <Card style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="mm-app-appr__head">
            <h3 className="title" style={{ margin: 0 }}>{cardTitle(current.summary)}</h3>
            <StatusBadge status={decided ? (approved ? 'approved' : 'fail') : 'pending'}>
              {decided ? (approved ? 'Approved' : 'Rejected') : 'Waiting'}
            </StatusBadge>
          </div>
          <p className="small" style={{ margin: '-8px 0 0', color: 'var(--ink-3)' }}>
            {`Made by the scheduler at ${shortTime(current.requested_at)} \u00b7 ${changes.length} works change`}
          </p>
          <div className="mm-app-appr__tags">
            {digs ? <Tag tone="lime" flat>{digs}</Tag> : null}
            {rainOld > rainNow ? <Tag tone="lime" flat>{`Rain hours ${rainOld} \u2192 ${rainNow}`}</Tag> : null}
          </div>
          <StepList
            steps={[
              rulesStep,
              { text: tier.text, detail: tier.detail, status: approved ? 'done' : 'needs' },
              { text: 'Department heads are told', detail: 'After you approve', status: approved ? 'done' : 'waiting' },
            ]}
          />
          <ul className="mm-app-appr__diffs">
            {changes.slice(0, 3).map((c) => (
              <DiffRow
                key={c.work_id}
                dept={c.dept}
                title={c.title}
                was={c.from_start != null && c.from_end != null ? dayRange(c.from_start, c.from_end) : undefined}
                to={dayRange(c.to_start, c.to_end)}
                reason={c.reason}
                cost={signedInr(c.cost_delta_inr)}
                costDir={c.cost_delta_inr > 0 ? 'up' : 'down'}
              />
            ))}
          </ul>
          <Link to="/approvals" className="small-strong">See all {changes.length} changes</Link>

          {failure ? <Banner tone="warn">{failure}</Banner> : null}
          {decided ? (
            approved
              ? <Banner tone="ok">Approved. Department heads are told.</Banner>
              : <Banner tone="warn">Rejected: {decided.reason}</Banner>
          ) : (
            <>
              <div ref={field}>
                <TextField
                  label="Reason"
                  hint="Needed only if you reject"
                  placeholder="What should change?"
                  value={reason}
                  error={error}
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
              <div className="mm-app-appr__actions">
                <Button variant="danger" icon="x" onClick={() => send('reject')} disabled={decide.isPending}>Reject</Button>
                <div style={{ flex: 1 }}>
                  <Button variant="primary" block onClick={() => send('approve')} disabled={decide.isPending}>Approve plan</Button>
                </div>
              </div>
            </>
          )}
        </Card>
      ) : (
        <div className="mm-app-appr__empty">
          <Icon name="sealCheck" size={24} />
          <p className="body" style={{ margin: 0 }}>Nothing is waiting for you.</p>
        </div>
      )}

      {history.length > 0 ? (
        <>
          <p className="mono-label" style={{ margin: 0, color: 'var(--ink-3)' }}>Earlier</p>
          {history.map((h) => (
            <Card key={h.key} flat style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div className="mm-app-appr__head">
                <span className="body-strong">{h.title}</span>
                <StatusBadge status={h.badge}>{h.word}</StatusBadge>
              </div>
              <span className="small" style={{ color: 'var(--ink-3)' }}>{h.line}</span>
            </Card>
          ))}
        </>
      ) : null}
    </div>
  );
}
