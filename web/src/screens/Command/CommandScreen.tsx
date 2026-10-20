import { useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { compareLabel, dayLabel, metricDelta, TODAY_DAY } from '../../api/format';
import type { MetricKind } from '../../api/format';
import {
  useApprovals, useNegotiation, useOldWayPlan, usePlanMetrics, useRiskWindows, useSegments, useShownPlan, useWorks,
} from '../../api/hooks';
import type { Metrics } from '../../api/types';
import { mapLegendCounts } from '../../map/geo';
import { PlanMap } from '../../map/PlanMap';
import type { PlanMapHandle } from '../../map/PlanMap';
import { useLiveEvent } from '../../api/live';
import { CopilotDock } from './CopilotDock';
import { NegotiationTab } from './NegotiationTab';
import { WorkDrawer } from './WorkDrawer';
import { WorksTab } from './WorksTab';
import { Button, Icon, MapLegend, MetricTile, Tabs, TimelineSlider, Toast, Toggle } from '../../ui';

const TABS = ['negotiation', 'works', 'risk', 'approvals'] as const;
type TabId = (typeof TABS)[number];

const WEEK_TICKS = ['2 Nov', '9 Nov', '16 Nov', '23 Nov'];

const TILES: { kind: MetricKind; field: keyof Metrics; label: string; unit?: string }[] = [
  { kind: 'digs_per_road', field: 'digs_per_road', label: 'Digs per road', unit: 'avg' },
  { kind: 'lane_closure_hours', field: 'lane_closure_hours', label: 'Lane-closure hours', unit: 'h' },
  { kind: 'clashes', field: 'clashes', label: 'Clashes left' },
  { kind: 'trench_hours_in_rain', field: 'trench_hours_in_rain', label: 'Trench-hours in rain', unit: 'h' },
  { kind: 'days_late', field: 'days_late', label: 'Days late', unit: 'days' },
];

const PART_TWO: Record<TabId, string> = {
  negotiation: 'Part 2 adds the live conversation between the department agents here.',
  works: 'Part 2 adds the list of works, with their dates and status, here.',
  risk: 'Part 2 adds the rain, air and event forecasts, with ways to change them, here.',
  approvals: 'Part 2 adds the plans waiting for approval, with approve and reject, here.',
};

export default function CommandScreen() {
  const [params, setParams] = useSearchParams();
  const [day, setDay] = useState(TODAY_DAY);
  const [showOldWay, setShowOldWay] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();
  const mapRef = useRef<PlanMapHandle>(null);

  const latestParams = useRef(params);
  latestParams.current = params;
  const tabParam = params.get('tab');
  const tab: TabId = TABS.find((t) => t === tabParam) ?? 'negotiation';
  const selectedWorkId = params.get('work');
  const setParam = (key: string, value: string | null) => {
    // Several actions can arrive in one tick, so each builds on the newest address, not on this render's.
    const next = new URLSearchParams(latestParams.current);
    if (value) next.set(key, value);
    else next.delete(key);
    latestParams.current = next;
    setParams(next, { replace: true });
  };

  const plan = useShownPlan().data;
  const old = useOldWayPlan().data;
  const views = useWorks(plan?.plan_id).data ?? [];
  const oldViews = useWorks(old?.plan_id).data ?? [];
  const metrics = usePlanMetrics(plan?.plan_id).data;
  const oldMetrics = usePlanMetrics(old?.plan_id).data;
  const windows = useRiskWindows().data ?? [];
  const segments = useSegments().data;
  const messages = useNegotiation().data ?? [];
  const pending = useApprovals('pending').data ?? [];

  useLiveEvent('ui.action', (data) => {
    const args = (data.args ?? {}) as Record<string, unknown>;
    const workId = typeof args.work_id === 'string' ? args.work_id : null;
    switch (data.action) {
      case 'select_work':
      case 'open_drawer':
        if (workId) setParam('work', workId);
        break;
      case 'set_day':
        setDay(Math.min(27, Math.max(0, Number(args.day) || 0)));
        break;
      case 'open_tab':
        if (TABS.some((t) => t === args.tab)) setParam('tab', String(args.tab));
        break;
      case 'fit_work':
        if (workId) mapRef.current?.fitWork(workId);
        break;
      case 'toggle_old_way':
        setShowOldWay(Boolean(args.on));
        break;
      case 'show_toast':
        clearTimeout(toastTimer.current);
        setToast(String(args.text ?? ''));
        toastTimer.current = setTimeout(() => setToast(null), 4000);
        break;
      default:
        break;
    }
  });

  const mapViews = showOldWay ? oldViews : views;
  const counts = useMemo(() => mapLegendCounts(mapViews, day), [mapViews, day]);

  const tabItems = [
    { id: 'negotiation', label: 'Negotiation', count: messages.length },
    { id: 'works', label: 'Works', count: views.length },
    { id: 'risk', label: 'Risk', count: windows.length },
    { id: 'approvals', label: 'Approvals', count: pending.length },
  ];

  return (
    <div className="mm-app-cmd">
      <div className="mm-app-cmd__map">
        <PlanMap
          ref={mapRef}
          views={mapViews}
          segments={segments}
          riskWindows={windows}
          day={day}
          selectedWorkId={selectedWorkId}
          onSelectWork={(id) => setParam('work', id)}
        />
      </div>

      <div className="mm-app-cmd__metrics">
        {TILES.map((t, i) => {
          const now = metrics ? Number(metrics[t.field]) : 0;
          const before = oldMetrics ? Number(oldMetrics[t.field]) : 0;
          const { delta, better } = metricDelta(now, before, t.kind);
          return (
            <div key={t.kind} className={i === TILES.length - 1 ? 'mm-app-cmd__tile mm-app-cmd__tile--last' : 'mm-app-cmd__tile'}>
              <MetricTile
                label={t.label}
                value={now}
                unit={t.unit}
                compare={oldMetrics ? compareLabel(before) : undefined}
                delta={delta}
                better={t.kind === 'days_late' ? now <= before : better}
              />
            </div>
          );
        })}
      </div>

      <div className="mm-app-cmd__legend">
        <MapLegend title={'On the map · ' + dayLabel(day)} counts={counts} />
      </div>

      <div className="mm-app-cmd__copilot">
        <div className="mm-app-cmd__copilot-in">
          <CopilotDock context={{ day, tab, selected_work: selectedWorkId, plan_id: plan?.plan_id }} />
        </div>
      </div>

      <div className="mm-app-cmd__timeline">
        <div className="mm-app-cmd__slider">
          <TimelineSlider
            days={28}
            value={day}
            onChange={setDay}
            valueLabel={dayLabel(day)}
            range="2–29 Nov"
            risks={windows.map((w) => ({ start: w.start_day, end: w.end_day + 1, kind: w.kind, label: w.label }))}
            tickLabel={(d) => WEEK_TICKS[d / 7] ?? ''}
          />
        </div>
        <span className="mm-app-cmd__divider" aria-hidden="true" />
        <Toggle checked={!showOldWay} onChange={(on) => setShowOldWay(!on)} off="Old way" on="MargaMitra" label="Compare with the old way" />
        <Button variant="ghost" icon="rain">Simulate rain</Button>
        <Button variant="secondary" icon="refresh">Re-plan</Button>
      </div>

      <aside className="mm-app-cmd__panel">
        <section className="mm-folder mm-app-cmd__folder">
          <div className="mm-folder__tab"><Icon name="handshake" size={16} />Plan for 2–29 Nov</div>
          <div className="mm-folder__body mm-app-cmd__body">
            <Tabs items={tabItems} value={tab} onChange={(id) => setParam('tab', id)} label="Plan panel" />
            {tab === 'negotiation' ? (
              <NegotiationTab onReview={() => setParam('tab', 'approvals')} />
            ) : tab === 'works' ? (
              <WorksTab />
            ) : (
              <p className="body" style={{ margin: 0, color: 'var(--ink-3)' }}>{PART_TWO[tab]}</p>
            )}
          </div>
        </section>
      </aside>

      {selectedWorkId ? (
        <WorkDrawer
          workId={selectedWorkId}
          onClose={() => setParam('work', null)}
          onFit={(id) => mapRef.current?.fitWork(id)}
        />
      ) : null}

      <div className="mm-app-cmd__toast">{toast ? <Toast icon="check">{toast}</Toast> : null}</div>
    </div>
  );
}