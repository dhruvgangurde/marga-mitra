import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { dayRange, deptName, inr, metres, signedInr, timeLabel, workStatusBadge } from '../../api/format';
import { useExplain, useLedger, useShownPlan, useVerification, useWhatIf, useWorks } from '../../api/hooks';
import type { WhatIfResult, WorkView } from '../../api/types';
import { Button, Card, DeptChip, DiffRow, Icon, IconButton, StatusBadge, StepList, TextField } from '../../ui';
import type { IconName } from '../../ui';

interface DrawerProps {
  workId: string;
  onClose: () => void;
  onFit: (workId: string) => void;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mono-label" style={{ color: 'var(--ink-3)' }}>{label}</div>
      <div className="body">{children}</div>
    </div>
  );
}

function DrawerBody({ view, partner, onClose, onFit }: { view: WorkView; partner?: WorkView; onClose: () => void; onFit: (id: string) => void }) {
  const { work, assignment, status } = view;
  const badge = workStatusBadge(status);
  const asideRef = useRef<HTMLElement>(null);
  const [text, setText] = useState(`${deptName((partner ?? view).work.dept)} starts 2 days late`);
  const [error, setError] = useState<string | undefined>();
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const whatIf = useWhatIf();
  const explain = useExplain(`work:${work.work_id}`).data;
  const ledger = useLedger(200).data ?? [];
  const verification = useVerification(work.work_id).data;
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    asideRef.current?.querySelector<HTMLElement>('button[aria-label="Close"]')?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      if (opener && document.contains(opener)) opener.focus();
    };
  }, []);

  const trap = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key !== 'Tab') return;
    const items = Array.from(asideRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const tryIt = () => {
    const found = text.match(/\d+/);
    const days = found ? Number(found[0]) : 0;
    if (days < 1 || days > 14) {
      setError('Use a number of days from 1 to 14');
      return;
    }
    setError(undefined);
    whatIf.mutate({ work_id: (partner ?? view).work.work_id, delay_days: days }, { onSuccess: setResult });
  };

  const moved = assignment && assignment.start_day !== work.requested_start;
  const oldEnd = work.requested_start + (work.modes[0]?.duration_days ?? 1) - 1;
  const dates = assignment ? dayRange(assignment.start_day, assignment.end_day) : 'Not planned';
  const mode = assignment?.mode ?? work.modes[0]?.mode;
  const seqs = new Set(explain?.ledger_seqs ?? []);
  const record = ledger
    .filter((e) => e.entity === `work:${work.work_id}` || seqs.has(e.seq))
    .sort((a, b) => b.seq - a.seq);

  return (
    <aside ref={asideRef} className="mm-app-drawer" aria-label={`Work ${work.work_id}`} onKeyDown={trap}>
      <header className="mm-app-drawer__head">
        <div className="mm-app-drawer__top">
          <DeptChip dept={work.dept} />
          <span className="mono" style={{ color: 'var(--ink-3)' }}>{work.work_id}</span>
          <StatusBadge status={badge.status}>{badge.label}</StatusBadge>
          <span style={{ marginLeft: 'auto' }}><IconButton icon="x" label="Close" onClick={onClose} /></span>
        </div>
        <h2 className="title-l" style={{ margin: 0 }}>{work.title}, {work.road_name}</h2>
        <div className="mm-app-drawer__facts">
          <Fact label="Dates">
            <span className="mono">
              {moved ? (
                <>
                  <s style={{ color: 'var(--ink-3)' }}>{dayRange(work.requested_start, oldEnd)}</s>
                  {' \u2192 '}
                  <b>{dates}</b>
                </>
              ) : dates}
            </span>
          </Fact>
          <Fact label="Length">{metres(work.length_m)}</Fact>
          <Fact label="Method">{mode === 'trenchless' ? 'Trenchless' : 'Open cut'}</Fact>
          <Fact label="Shared with">{partner ? `${deptName(partner.work.dept)} \u00b7 ${partner.work.work_id}` : 'No'}</Fact>
          <Fact label="Department">{deptName(work.dept)}</Fact>
          <Fact label="Deposit"><span className="mono">{inr(work.deposit_inr)} {status === 'verified' ? 'released' : 'held'}</span></Fact>
        </div>
      </header>

      <div className="mm-app-drawer__body">
        <section>
          <h3 className="display-3" style={{ margin: '0 0 12px', color: 'var(--maroon)' }}>Why these dates?</h3>
          <ol className="mm-app-drawer__reasons">
            {(explain?.reasons ?? []).map((r, i) => (
              <li key={i} className="mm-app-drawer__reason">
                <span className="mm-app-drawer__dot"><Icon name={r.icon as IconName} size={16} /></span>
                <span>
                  <span className="body"><b>{r.lead}</b> {r.text}</span>
                  <span className="small" style={{ display: 'block', color: 'var(--ink-3)' }}>Source: {r.source}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <h3 className="title" style={{ margin: '0 0 12px' }}>Rules check</h3>
          <StepList steps={(explain?.rules ?? []).map((r) => ({ text: r.name, detail: r.detail, status: r.severity === 'ok' ? 'done' : 'needs' }))} />
        </section>

        <Card soft>
          <div className="mm-app-drawer__whatif">
            <h3 className="title" style={{ margin: 0 }}>What if</h3>
            <TextField
              label="Change one thing and see the new plan"
              value={text}
              error={error}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="mm-app-drawer__row">
              <Button variant="secondary" icon="refresh" onClick={tryIt} disabled={whatIf.isPending}>Try it</Button>
              <Button variant="ghost" aria-label="Clear the what-if result. Nothing is saved." onClick={() => { setResult(null); setError(undefined); }}>
                Nothing is saved
              </Button>
            </div>
            {result ? (
              <div>
                <ul className="mm-app-drawer__diffs">
                  {result.diff.map((c) => (
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
                <p className="small" style={{ margin: '8px 0 0', color: 'var(--ink-3)' }}>
                  Days late would be {result.metrics.days_late}. Nothing is saved.
                </p>
              </div>
            ) : null}
          </div>
        </Card>

        <section>
          <h3 className="title" style={{ margin: '0 0 8px' }}>In the public record</h3>
          <ul className="mm-app-drawer__record">
            {record.map((e) => (
              <li key={e.seq} className="mm-app-drawer__entry">
                <span className="mono" style={{ width: 44, color: 'var(--ink-3)' }}>#{e.seq}</span>
                <span className="body" style={{ flex: 1 }}>{e.summary}</span>
                <span className="mono" style={{ color: 'var(--ink-3)' }}>{timeLabel(e.ts)}</span>
              </li>
            ))}
          </ul>
          <Link to="/record" className="small-strong">Check the record</Link>
        </section>
      </div>

      <footer className="mm-app-drawer__foot">
        <Button variant="secondary" icon="pin" onClick={() => onFit(work.work_id)}>Show on map</Button>
        <Button variant="secondary" icon="camera" as="a" href={verification ? `/field/${work.work_id}/result` : `/field/${work.work_id}`}>See photos</Button>
      </footer>
    </aside>
  );
}

export function WorkDrawer({ workId, onClose, onFit }: DrawerProps) {
  const plan = useShownPlan().data;
  const views = useWorks(plan?.plan_id).data ?? [];
  const view = views.find((v) => v.work.work_id === workId);
  if (!view) return null;
  const group = view.assignment?.shared_group;
  const partner = group ? views.find((v) => v.work.work_id !== workId && v.assignment?.shared_group === group) : undefined;
  return <DrawerBody key={workId} view={view} partner={partner} onClose={onClose} onFit={onFit} />;
}