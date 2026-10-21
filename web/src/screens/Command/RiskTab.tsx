import { aqiBand, dayRange, signedInr } from '../../api/format';
import {
  useHealth, useOldWayPlan, usePlanDiff, usePlanMetrics, useRiskWindows, useSegments, useShownPlan, useWorks,
} from '../../api/hooks';
import type { RiskWindow } from '../../api/types';
import { Banner, Button, Card, DiffRow, Icon, StatusBadge, Tag } from '../../ui';
import type { IconName } from '../../ui';

const EVENT_DETAILS: Record<string, string> = {
  'EV-DEMO': 'NH-66 service road closed 16:00\u201322:00',
};

const cardStyle = (gap: number) => ({ display: 'flex', flexDirection: 'column' as const, gap });

function Dot({ color, icon }: { color: string; icon: IconName }) {
  return <span className="mm-app-risk__dot" style={{ background: color }}><Icon name={icon} size={16} /></span>;
}

const title = (w: RiskWindow): string => w.label.replace(', ', ' \u00b7 ');

// Where a rain or air window came from.
function SourceBadge({ source }: { source: RiskWindow['source'] }) {
  if (source === 'override') return <StatusBadge status="warn">Simulated</StatusBadge>;
  if (source === 'open-meteo') return <StatusBadge status="live">Live forecast</StatusBadge>;
  return <StatusBadge status="pending">Demo forecast</StatusBadge>;
}

export function RiskTab({ onReview }: { onReview: () => void }) {
  const windows = useRiskWindows().data ?? [];
  const plan = useShownPlan().data;
  const old = useOldWayPlan().data;
  const views = useWorks(plan?.plan_id).data ?? [];
  const diff = usePlanDiff(plan?.plan_id, plan?.base_plan_id ?? undefined).data;
  const planMetrics = usePlanMetrics(plan?.plan_id).data;
  const oldMetrics = usePlanMetrics(old?.plan_id).data;
  const mode = useHealth().data?.weather_mode;
  const segments = useSegments().data;

  const changes = plan?.base_plan_id ? diff ?? [] : [];
  const override = windows.some((w) => w.kind === 'rain' && w.source === 'override');
  const replanned = plan?.status === 'waiting_approval' && Boolean(plan.base_plan_id);

  // Where the forecast comes from, as /health and the windows say.
  const weather = windows.filter((w) => w.kind === 'rain' || w.kind === 'air');
  let source: React.ReactNode = null;
  if (mode === 'fixture') {
    source = (
      <div style={cardStyle(6)}>
        <div><Tag flat>Demo forecast</Tag></div>
        <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>
          A hand-made forecast for the demo. Live forecasts come from Open-Meteo.
        </p>
      </div>
    );
  } else if (mode === 'live') {
    source = weather.some((w) => w.source === 'fixture')
      ? <Banner tone="warn" title="Live forecast unavailable">Showing the demo forecast until it is back.</Banner>
      : <div><Tag tone="lime" flat>{'Live forecast \u00b7 Open-Meteo'}</Tag></div>;
  }

  // The first two road names of an event's segments.
  const roads = (ids: string[]): string => {
    const names = new Set<string>();
    for (const f of segments?.features ?? []) {
      if (ids.includes(f.properties.segment_id) && f.properties.name) names.add(f.properties.name);
    }
    const list = [...names].slice(0, 2);
    return list.length ? list.join(', ') : `${ids.length} road segments`;
  };

  if (windows.length === 0) {
    return (
      <div className="mm-app-risk">
        {source}
        <div className="mm-app-risk__empty">
          <Icon name="rain" size={24} />
          <p className="body" style={{ margin: 0 }}>No rain, air or event risk in the next 4 weeks.</p>
        </div>
      </div>
    );
  }

  const simulated = windows.find((w) => w.kind === 'rain' && w.source === 'override');

  return (
    <div className="mm-app-risk">
      {source}
      {override && simulated ? (
        <Banner tone="warn" title="Simulated forecast">
          {`${simulated.value} mm of rain in 24 hours on ${dayRange(simulated.start_day, simulated.end_day)}, added for the demo. Live forecasts come from Open-Meteo.`}
        </Banner>
      ) : null}

      {replanned && plan ? (
        <>
          <Banner tone="ok" title={`Re-planned in ${(plan.solve_ms / 1000).toFixed(1)} s`}>
            {`Trench-hours in rain: ${oldMetrics?.trench_hours_in_rain ?? 0} \u2192 ${planMetrics?.trench_hours_in_rain ?? 0}. Waiting for your approval.`}
          </Banner>
          <Button variant="primary" block onClick={onReview}>Review and approve</Button>
        </>
      ) : null}

      {windows.filter((w) => w.kind === 'rain').map((w) => (
        <Card key={w.window_id} style={cardStyle(12)}>
          <div className="mm-app-risk__head">
            <Dot color="var(--risk-rain)" icon="rain" />
            <h3 className="title" style={{ margin: 0 }}>{title(w)}</h3>
            <span style={{ marginLeft: 'auto' }}>
              <SourceBadge source={w.source} />
            </span>
          </div>
          <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>
            {`${w.value} mm in 24 hours`}
          </p>
          {changes.length > 0 ? (
            <>
              <p className="body-strong" style={{ margin: 0 }}>{changes.length} works on low-lying roads moved out of the rain</p>
              <ul className="mm-app-risk__diffs">
                {changes.map((c) => (
                  <DiffRow
                    key={c.work_id}
                    dept={c.dept}
                    title={c.title}
                    was={c.from_start != null && c.from_end != null ? dayRange(c.from_start, c.from_end) : undefined}
                    to={dayRange(c.to_start, c.to_end)}
                    reason={c.reason}
                    cost={signedInr(c.cost_delta_inr)}
                    costDir="up"
                  />
                ))}
              </ul>
            </>
          ) : null}
        </Card>
      ))}

      {windows.filter((w) => w.kind === 'event').map((w) => {
        const hit = views.filter((v) => v.assignment
          && v.assignment.start_day <= w.end_day && v.assignment.end_day >= w.start_day
          && v.work.segment_ids.some((s) => w.segment_ids.includes(s))).length;
        return (
          <Card key={w.window_id} style={cardStyle(8)}>
            <div className="mm-app-risk__head">
              <Dot color="var(--risk-event)" icon="flag" />
              <h3 className="title" style={{ margin: 0 }}>{title(w)}</h3>
              <span style={{ marginLeft: 'auto' }}><StatusBadge status="ok">No change</StatusBadge></span>
            </div>
            <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>{EVENT_DETAILS[w.window_id] ?? `${dayRange(w.start_day, w.end_day)} \u00b7 ${roads(w.segment_ids)}`}</p>
            <p className="body" style={{ margin: 0 }}>
              {hit === 0 ? 'No work is planned on that road that day.' : `${hit} works are planned on that road that day.`}
            </p>
          </Card>
        );
      })}

      {windows.filter((w) => w.kind === 'air').map((w) => (
        <Card key={w.window_id} style={cardStyle(8)}>
          <div className="mm-app-risk__head">
            <Dot color="var(--risk-air)" icon="wind" />
            <h3 className="title" style={{ margin: 0 }}>{title(w)}</h3>
            <span style={{ marginLeft: 'auto' }}><SourceBadge source={w.source} /></span>
          </div>
          <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>{`AQI ${w.value} \u00b7 ${aqiBand(w.value)}`}</p>
          <p className="body" style={{ margin: 0 }}>Dusty open cuts are kept out of these days.</p>
        </Card>
      ))}
    </div>
  );
}
