import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { USE_MOCKS } from '../../api/client';
import { useAuditorFlags, useLedger, useNoDig, useVerifyLedger, useWorks } from '../../api/hooks';
import { actorLabel, linkLabel, shortTime, timeLabel } from '../../api/format';
import type { LedgerEntry, NoDigEntry } from '../../api/types';
import { Banner, Button, Card, DataTable, EmptyState, LoadError, MetricTile, Skeleton, StatusBadge, Tag } from '../../ui';

const MOST_SHOWN = 500;
const COLUMN = { display: 'flex', flexDirection: 'column', gap: 16 } as const;
const HALF = { flex: '1 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 } as const;
const untilDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' });

const LEDGER_COLUMNS = [
  { key: 'seq', label: '#', mono: true, num: true },
  { key: 'time', label: 'Time', mono: true },
  { key: 'who', label: 'Who' },
  { key: 'what', label: 'What happened' },
  { key: 'work', label: 'Work', mono: true },
  { key: 'link', label: 'Link', mono: true },
];

const NO_DIG_COLUMNS = [
  { key: 'road', label: 'Road' },
  { key: 'until', label: 'Protected until', mono: true },
  { key: 'why', label: 'Why' },
];

function workOf(e: LedgerEntry): string {
  if (e.entity.startsWith('work:')) return e.entity.slice('work:'.length);
  return typeof e.payload.work_id === 'string' ? e.payload.work_id : '—';
}

// One row per road name: the first entry of each name.
function byRoad(list: NoDigEntry[]): NoDigEntry[] {
  return list.filter((e, i) => list.findIndex((x) => x.name === e.name) === i);
}

export default function RecordScreen() {
  const [search] = useSearchParams();
  const [limit, setLimit] = useState(10);
  const ledger = useLedger(limit);
  const works = useWorks();
  const noDig = useNoDig();
  const flags = useAuditorFlags();
  const verify = useVerifyLedger();
  // Keeps the last rows on screen while a bigger page loads.
  const shownRows = useRef<LedgerEntry[]>([]);
  const checkedOnce = useRef(false);

  if (ledger.data) shownRows.current = ledger.data;
  const entries = shownRows.current;
  const total = entries[0]?.seq ?? 0;
  const roads = byRoad(noDig.data ?? []);
  const result = verify.data;
  const queries = [ledger, works, noDig, flags];
  const ledgerLoading = ledger.isLoading && entries.length === 0;
  const loading = ledgerLoading || works.isLoading || noDig.isLoading || flags.isLoading;

  const runCheck = verify.mutate;
  useEffect(() => {
    if (!USE_MOCKS || checkedOnce.current || search.get('checked') !== '1') return;
    checkedOnce.current = true;
    runCheck();
  }, [search, runCheck]);

  return (
    <main
      aria-busy={loading ? 'true' : undefined}
      style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px 96px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 64 }}
    >
      <LoadError queries={queries} />
      <section style={{ ...COLUMN, alignItems: 'flex-start' }}>
        <Tag>Open to everyone</Tag>
        <h1 className="display-2" style={{ margin: 0, color: 'var(--maroon)' }}>Public record</h1>
        <p className="body-l" style={{ margin: 0, maxWidth: 720, color: 'var(--ink-2)' }}>
          Every plan, approval, photo check and payment for Surathkal, in order. Each entry is linked to the one before it,
          so changing any old entry breaks every link after it.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', width: '100%' }}>
          <Button variant="primary" disabled={verify.isPending} onClick={() => verify.mutate()}>Check the record</Button>
          {/* Always present, so the check result is announced when it arrives. */}
          <div aria-live="polite" style={verify.isError || result ? { flex: '1 1 420px', minWidth: 0 } : undefined}>
            {verify.isError ? (
              <Banner tone="danger" title="Could not send">Check your connection and try again.</Banner>
            ) : result?.ok ? (
              <Banner tone="ok" title="Record checked">{`${result.entries} entries. Nothing was changed.`}</Banner>
            ) : result ? (
              <Banner tone="danger" title="The record was changed">
                {`Entry #${result.first_bad_seq} no longer matches what was written, so every entry after it is unlinked.`}
              </Banner>
            ) : (
              <span className="small" style={{ color: 'var(--ink-3)' }}>Anyone can run this check.</span>
            )}
          </div>
        </div>
        {loading ? <div style={{ width: '100%' }}><Skeleton height={120} /></div> : queries.some((q) => q.isError) ? null : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, width: '100%' }}>
          <div style={{ flex: '1 1 200px', minWidth: 0 }}><MetricTile label="Entries" value={total} /></div>
          <div style={{ flex: '1 1 200px', minWidth: 0 }}><MetricTile label="Works this month" value={works.data?.length ?? 0} /></div>
          <div style={{ flex: '1 1 200px', minWidth: 0 }}><MetricTile label="Protected roads" value={roads.length} /></div>
          <div style={{ flex: '1 1 200px', minWidth: 0 }}><MetricTile label="Auditor notes" value={flags.data?.length ?? 0} /></div>
        </div>
        )}
      </section>

      <section style={COLUMN}>
        <h2 className="display-3" style={{ margin: 0 }}>Latest entries</h2>
        {ledgerLoading ? <Skeleton height={120} /> : entries.length === 0 && ledger.isError ? null : entries.length === 0 ? (
          <EmptyState icon="eye" text="The record is empty." action={<Button as="a" href="/command">Open command centre</Button>} />
        ) : (
        <Card style={{ padding: 0, overflowX: 'auto' }}>
          <DataTable
            caption="Newest first"
            columns={LEDGER_COLUMNS}
            rows={entries.map((e) => ({
              id: e.seq, seq: e.seq, time: timeLabel(e.ts), who: actorLabel(e.actor), what: e.summary, work: workOf(e), link: linkLabel(e.hash),
            }))}
          />
        </Card>
        )}
        {entries.length < Math.min(total, MOST_SHOWN) ? (
          <div><Button variant="ghost" onClick={() => setLimit(Math.min(total, MOST_SHOWN))}>{`Show all ${total} entries`}</Button></div>
        ) : null}
      </section>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 32, alignItems: 'flex-start' }}>
        <section style={HALF}>
          <h2 className="display-3" style={{ margin: 0 }}>Protected roads</h2>
          <p className="body" style={{ margin: 0, color: 'var(--ink-2)' }}>
            No new digs on these roads until the date shown. Emergencies are allowed and reviewed after.
          </p>
          {noDig.isLoading ? <Skeleton height={120} /> : noDig.isError ? null : (
            <Card style={{ padding: 0, overflowX: 'auto' }}>
              <DataTable
                caption="Protected-road list"
                columns={NO_DIG_COLUMNS}
                rows={roads.map((r) => ({ id: r.name, road: r.name, until: untilDate.format(new Date(r.protected_until)), why: r.why }))}
              />
            </Card>
          )}
        </section>

        <section style={HALF}>
          <h2 className="display-3" style={{ margin: 0 }}>Auditor notes</h2>
          <p className="body" style={{ margin: 0, color: 'var(--ink-2)' }}>
            The auditor reads every entry and flags anything a person should look at.
          </p>
          {flags.isLoading ? <Skeleton height={120} /> : null}
          {(flags.data ?? []).map((f) => (
            <Card key={f.flag_id} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <StatusBadge status={f.severity}>{f.word}</StatusBadge>
                {f.work_id ? <span className="mono" style={{ color: 'var(--ink-3)' }}>{f.work_id}</span> : null}
                <span className="mono" style={{ color: 'var(--ink-3)', marginLeft: 'auto' }}>{shortTime(f.created_at)}</span>
              </div>
              <p className="body" style={{ margin: 0 }}>{f.text}</p>
            </Card>
          ))}
        </section>
      </div>
    </main>
  );
}
