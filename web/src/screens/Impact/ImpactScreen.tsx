import { useEvalsSummary } from '../../api/hooks';
import { compareLabel, metricDelta } from '../../api/format';
import type { MetricKind } from '../../api/format';
import type { EvalRow, EvalSummary, Stat } from '../../api/types';
import { Button, Card, DataTable, MetricTile, Tag } from '../../ui';

type Variant = EvalRow['variant'];
type StatKey = 'digs_per_road' | 'lane_closure_hours' | 'trench_hours_in_rain' | 'clashes' | 'days_late';

const SAND = 'var(--sand)';
const MAROON_SOFT = 'var(--maroon-soft)';
const LIME = 'var(--lime)';
const COLUMN = { display: 'flex', flexDirection: 'column', gap: 16 } as const;
const LEAD = { margin: 0, maxWidth: 760, color: 'var(--ink-2)' } as const;

const oneDecimal = (v: number) => v.toFixed(1);
const trimmed = (v: number) => v.toFixed(1).replace(/\.0$/, '');
const whole = (v: number) => Math.round(v).toLocaleString('en-IN');
const range = (s: Stat, f: (v: number) => string) => `${f(s.median)} (${f(s.low)}–${f(s.high)})`;

const SETUPS: { variant: Variant; label: string }[] = [
  { variant: 'naive', label: 'Old way (first come, first dug)' },
  { variant: 'solver_only', label: 'Scheduler without agents' },
  { variant: 'agents', label: '+ department agents' },
  { variant: 'risk', label: '+ rain, air and event forecasts' },
  { variant: 'full', label: '+ photo checks (all of MargaMitra)' },
];

const TILES: { label: string; key: StatKey & MetricKind; unit: string; round: (v: number) => number }[] = [
  { label: 'Digs per road', key: 'digs_per_road', unit: 'avg', round: (v) => Number(oneDecimal(v)) },
  { label: 'Lane-closure hours', key: 'lane_closure_hours', unit: 'h', round: Math.round },
  { label: 'Trench-hours in rain', key: 'trench_hours_in_rain', unit: 'h', round: Math.round },
  { label: 'Days late', key: 'days_late', unit: 'days', round: (v) => Number(oneDecimal(v)) },
];

const BARS: { label: string; key: StatKey; format: (v: number) => string }[] = [
  { label: 'Digs per road', key: 'digs_per_road', format: oneDecimal },
  { label: 'Lane-closure hours', key: 'lane_closure_hours', format: (v) => `${whole(v)} h` },
  { label: 'Trench-hours in rain', key: 'trench_hours_in_rain', format: (v) => `${whole(v)} h` },
  { label: 'Clashes', key: 'clashes', format: trimmed },
];

const TABLE_COLUMNS = [
  { key: 'setup', label: 'What is switched on' },
  { key: 'digs', label: 'Digs per road', num: true, mono: true },
  { key: 'lane', label: 'Lane-closure hours', num: true, mono: true },
  { key: 'rain', label: 'Trench-hours in rain', num: true, mono: true },
  { key: 'late', label: 'Days late', num: true, mono: true },
  { key: 'fake', label: 'Fake repairs caught', num: true, mono: true },
];

function Swatch({ fill }: { fill: string }) {
  return (
    <span
      style={{
        width: 14, height: 14, boxSizing: 'border-box', borderRadius: 'var(--radius-xs)',
        border: 'var(--stroke-ui) solid var(--ink)', background: fill,
      }}
    />
  );
}

function Bar({ fill, pct, value }: { fill: string; pct: number; value: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span
        aria-hidden="true"
        style={{
          display: 'block', flex: '0 1 auto', height: 18, boxSizing: 'border-box', border: 'var(--stroke-ui) solid var(--ink)',
          borderRadius: 'var(--radius-xs)', background: fill, width: Math.max(2, pct) + '%',
        }}
      />
      {/* No wrap, so the full old-way bar shrinks instead of breaking "1,096 h" over two lines. */}
      <span className="mono" style={{ whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

// Share of the old-way value; with an old-way value of 0 a bar is full when there is anything at all.
const share = (value: number, old: number) => (old === 0 ? (value > 0 ? 100 : 2) : (value / old) * 100);

function Report({ summary }: { summary: EvalSummary }) {
  const n = summary.seeds.length;
  const row = (v: Variant) => summary.rows.find((r) => r.variant === v);
  const naive = row('naive');
  const solo = row('solver_only');
  const full = row('full');

  return (
    <>
      <section style={{ ...COLUMN, alignItems: 'flex-start' }}>
        <Tag>{`Across ${n} test cases`}</Tag>
        <h1 className="display-2" style={{ margin: 0, color: 'var(--ink)' }}>
          What changes when roads are dug{' '}
          <span className="script-accent" style={{ color: 'var(--maroon)', textTransform: 'none' }}>once</span>
        </h1>
        <p className="body-l" style={LEAD}>
          {`We planned the same works two ways in ${n} test cases on Surathkal's real roads: the old way, where each department books first come, first dug, and with MargaMitra. These are the middle values; the range is in brackets.`}
        </p>
        {naive && full ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, width: '100%' }}>
            {TILES.map((t) => {
              const now = t.round(full[t.key].median);
              const old = t.round(naive[t.key].median);
              return (
                <div key={t.key} style={{ flex: '1 1 220px', minWidth: 0 }}>
                  <MetricTile label={t.label} value={now} unit={t.unit} compare={compareLabel(old)} {...metricDelta(now, old, t.key)} />
                </div>
              );
            })}
          </div>
        ) : null}
      </section>

      {naive && solo && full ? (
        <section aria-labelledby="impact-chart-title">
          <Card style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: 24 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'baseline', justifyContent: 'space-between' }}>
              <h2 id="impact-chart-title" className="display-3" style={{ margin: 0 }}>Old way and MargaMitra, side by side</h2>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }} aria-hidden="true">
                {[[SAND, 'Old way'], [MAROON_SOFT, 'Scheduler without agents'], [LIME, 'MargaMitra']].map(([fill, label]) => (
                  <span key={label} className="small" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <Swatch fill={fill} />{label}
                  </span>
                ))}
              </div>
            </div>
            {BARS.map((b) => {
              const old = naive[b.key].median;
              return (
                <div
                  key={b.key}
                  role="group"
                  aria-label={b.label}
                  style={{ display: 'grid', gridTemplateColumns: '200px minmax(0, 1fr)', gap: '8px 16px', alignItems: 'center' }}
                >
                  <span className="body-strong" style={{ gridRow: 'span 3' }}>{b.label}</span>
                  <Bar fill={SAND} pct={100} value={b.format(old)} />
                  <Bar fill={MAROON_SOFT} pct={share(solo[b.key].median, old)} value={b.format(solo[b.key].median)} />
                  <Bar fill={LIME} pct={share(full[b.key].median, old)} value={b.format(full[b.key].median)} />
                </div>
              );
            })}
          </Card>
        </section>
      ) : null}

      <section style={COLUMN}>
        <h2 className="display-3" style={{ margin: 0 }}>What each part adds</h2>
        <p className="body" style={LEAD}>
          We switched the parts on one at a time. The scheduler alone removes most clashes; the agents find shared trenches;
          the forecasts keep trenches out of the rain; the photo checks catch fake repairs.
        </p>
        <Card style={{ padding: 0, overflowX: 'auto' }}>
          <DataTable
            caption={`Middle value across ${n} test cases (range)`}
            columns={TABLE_COLUMNS}
            rows={SETUPS.flatMap(({ variant, label }) => {
              const r = row(variant);
              return r ? [{
                id: variant,
                setup: label,
                digs: range(r.digs_per_road, oneDecimal),
                lane: range(r.lane_closure_hours, whole),
                rain: range(r.trench_hours_in_rain, whole),
                late: trimmed(r.days_late.median),
                fake: variant === 'full' ? `${summary.fake_repairs_caught} of ${summary.fake_repairs_total}` : '—',
              }] : [];
            })}
          />
        </Card>
      </section>

      <section style={COLUMN}>
        <h2 className="display-3" style={{ margin: 0 }}>How we tested</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
          {[
            ['Test cases', "Each test case uses Surathkal's real roads with 14 to 20 random works from 6 departments over 28 days, and always includes clashes."],
            ['Same inputs', 'Both ways plan exactly the same works with the same forecasts. Only the planning changes.'],
            ['Repeatable', `Every number on this page is produced by the test code in the project, for test cases 1 to ${n}.`],
          ].map(([title, text]) => (
            <Card key={title} flat style={{ flex: '1 1 300px', minWidth: 0, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span className="mono-label" style={{ color: 'var(--ink-3)' }}>{title}</span>
              <span className="body">{text}</span>
            </Card>
          ))}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 16 }}>
          <Button variant="primary" as="a" href="/command">Open command centre</Button>
          <Button icon="eye" as="a" href="/record">See the public record</Button>
        </div>
      </section>
    </>
  );
}

export default function ImpactScreen() {
  const summary = useEvalsSummary().data;
  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px 96px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 64 }}>
      {summary ? <Report summary={summary} /> : null}
    </main>
  );
}
