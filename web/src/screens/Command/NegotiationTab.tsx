import { useEffect, useRef } from 'react';
import { dayDate, dayLabel, recipientLabel, signedInr, timeLabel } from '../../api/format';
import { useNegotiation, useOldWayPlan, useOrchestrate, useRun, useShownPlan, useWorks } from '../../api/hooks';
import { useFreshIds } from '../../api/live';
import { Banner, Button, Icon, NegotiationMessage, StatusBadge } from '../../ui';

// "Option A. Munchur Road: 4 digs become 2, lane-closure hours ..." becomes "Munchur Road: 4 digs become 2".
function planReadyText(body: string): string {
  const text = body.replace(/^Option [A-Z]\.\s*/, '');
  const cut = text.search(/[,.]/);
  return (cut >= 0 ? text.slice(0, cut) : text) + '. Rules check passed.';
}

export function NegotiationTab({ onReview }: { onReview: () => void }) {
  const messages = useNegotiation().data ?? [];
  const fresh = useFreshIds();
  const orchestrate = useOrchestrate();
  const runId = messages[0]?.run_id;
  const run = useRun(runId).data;
  const plan = useShownPlan().data;
  const old = useOldWayPlan().data;
  const views = useWorks(plan?.plan_id).data ?? [];
  const oldViews = useWorks(old?.plan_id).data ?? [];

  const end = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    const box = end.current?.closest('.mm-app-cmd__body');
    if (!box) return undefined;
    const onScroll = () => {
      stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 48;
    };
    box.addEventListener('scroll', onScroll);
    return () => box.removeEventListener('scroll', onScroll);
  }, []);
  useEffect(() => {
    if (stick.current) end.current?.scrollIntoView({ block: 'end' });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="mm-app-neg">
        <div className="mm-app-neg__empty">
          <Icon name="handshake" size={24} />
          <p className="title" style={{ margin: 0 }}>No plan yet</p>
          <p className="body" style={{ margin: 0, color: 'var(--ink-2)' }}>Make one plan for all departments.</p>
          <Button variant="primary" onClick={() => orchestrate.mutate()} disabled={orchestrate.isPending}>Orchestrate</Button>
        </div>
        <div ref={end} />
      </div>
    );
  }

  const notice = messages.find((m) => m.type === 'NOTICE') ?? messages[0];
  const decision = messages.find((m) => m.type === 'DECISION');
  const round = Math.max(...messages.map((m) => m.round));
  let status = run?.status;
  if (decision && (!status || status === 'running')) status = 'waiting_approval';
  const running = !decision && (!status || status === 'running');

  const road = views.find((v) => v.work.work_id === notice.work_ids[0])?.work.road_name ?? '';
  const spans = oldViews
    .filter((v) => notice.work_ids.includes(v.work.work_id) && v.assignment)
    .map((v) => [v.assignment!.start_day, v.assignment!.end_day]);
  const first = spans.length ? Math.min(...spans.map((s) => s[0])) : null;
  const last = spans.length ? Math.max(...spans.map((s) => s[1])) : null;
  const clash = `${notice.work_ids.length} works clash` + (first !== null && last !== null
    ? ` between ${dayDate(first).getUTCDate()} and ${dayLabel(last)}` : '') + '.';

  const badge =
    status === 'approved' ? <StatusBadge status="approved">Approved</StatusBadge>
      : status === 'rejected' || status === 'failed' ? <StatusBadge status="fail">Rejected</StatusBadge>
        : running ? <StatusBadge status="live">{`Round ${round} of 3`}</StatusBadge>
          : <StatusBadge status="pending">Waiting for your approval</StatusBadge>;

  return (
    <div className="mm-app-neg">
      <div className="mm-app-neg__head">
        <h2 className="display-3" style={{ margin: 0, color: 'var(--maroon)' }}>{road}</h2>
        {badge}
      </div>
      <p className="body" style={{ margin: '-8px 0 0', color: 'var(--ink-3)' }}>
        {running
          ? `${clash} The department agents are agreeing on dates.`
          : `The departments agreed in ${round} ${round === 1 ? 'round' : 'rounds'}.`}
      </p>
      <div className="mm-app-neg__list" aria-live="polite">
        {messages.map((m) => (
          <NegotiationMessage
            key={m.msg_id}
            sender={m.sender}
            to={m.recipients.map(recipientLabel).join(', ')}
            type={m.type}
            round={m.round}
            time={timeLabel(m.ts)}
            body={m.body}
            options={m.type === 'COUNTER' ? m.options.map((o) => ({ label: o.label, cost: signedInr(o.cost_delta_inr) })) : undefined}
            fresh={fresh.has(m.msg_id)}
          />
        ))}
      </div>
      {decision && status === 'waiting_approval' ? (
        <>
          <Banner tone="ok" title="Plan ready for your approval">{planReadyText(decision.body)}</Banner>
          <Button variant="primary" block onClick={onReview}>Review and approve</Button>
        </>
      ) : null}
      <div ref={end} />
    </div>
  );
}