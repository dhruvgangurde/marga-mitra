import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { compareLabel, dayLabel, errorText, metricDelta, TODAY_DAY } from '../../api/format';
import type { MetricKind } from '../../api/format';
import {
  useApprovals, useForecastOverride, useNegotiation, useOrchestrate, useOldWayPlan, usePlanBusy, usePlanDiff, usePlanMetrics, useRiskWindows, useSegments, useShownPlan, useWorks,
} from '../../api/hooks';
import type { Metrics } from '../../api/types';
import { mapLegendCounts } from '../../map/geo';
import { PlanMap } from '../../map/PlanMap';
import type { PlanMapHandle } from '../../map/PlanMap';
import { useLiveEvent } from '../../api/live';
import { CopilotDock } from './CopilotDock';
import { NegotiationTab } from './NegotiationTab';
import { ApprovalsTab } from './ApprovalsTab';
import { RiskTab } from './RiskTab';
import { WorkDrawer } from './WorkDrawer';
import { WorksTab } from './WorksTab';
import { Banner, Button, Card, Icon, MapLegend, MetricTile, Tabs, TimelineSlider, Toast, Toggle } from '../../ui';

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

export default function CommandScreen() {
  const [params, setParams] = useSearchParams();
  const [day, setDay] = useState(() => {
    const asked = Number(params.get('day'));
    return params.get('day') !== null && asked >= 0 && asked <= 27 ? Math.floor(asked) : TODAY_DAY;
  });
  const [showOldWay, setShowOldWay] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [folded, setFolded] = useState(false);
  const [toast, setToast] = useState<{ text: string; view: boolean } | null>(null);
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

  const planQ = useShownPlan();
  const plan = planQ.data;
  const old = useOldWayPlan().data;
  const worksQ = useWorks(plan?.plan_id);
  const views = worksQ.data ?? [];
  const oldViews = useWorks(old?.plan_id).data ?? [];
  const metrics = usePlanMetrics(plan?.plan_id).data;
  const oldMetrics = usePlanMetrics(old?.plan_id).data;
  const windows = useRiskWindows().data ?? [];
  const segments = useSegments().data;
  const messages = useNegotiation().data ?? [];
  const pending = useApprovals('pending').data ?? [];

  // Only one toast shows at a time; it hides after 6 s.
  const showToast = (text: string, view: boolean) => {
    clearTimeout(toastTimer.current);
    setToast({ text, view });
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  };
  // The rain toast waits for the new plan and its changes, so the count is the real one.
  const rainToast = useRef<string | null>(params.get('demo') === 'rain' ? '' : null);
  const rainDiff = usePlanDiff(plan?.plan_id, plan?.base_plan_id ?? undefined).data;
  useEffect(() => () => clearTimeout(toastTimer.current), []);
  useEffect(() => {
    if (rainToast.current === null || !plan || !rainDiff) return;
    if (plan.status !== 'waiting_approval' || !plan.base_plan_id || plan.plan_id === rainToast.current) return;
    rainToast.current = null;
    showToast(`Plan updated. ${rainDiff.length} works moved out of the rain window.`, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, rainDiff]);
  useLiveEvent('plan.updated', (data) => {
    const hasRain = windows.some((w) => w.kind === 'rain' && w.source === 'override');
    if (data.status === 'waiting_approval' && hasRain) rainToast.current = plan?.plan_id ?? '';
  });
  // Play steps the day forward every 700 ms and stops at the last day.
  useEffect(() => {
    if (!playing) return undefined;
    const timer = setInterval(() => setDay((d) => Math.min(27, d + 1)), 700);
    return () => clearInterval(timer);
  }, [playing]);
  useEffect(() => {
    if (playing && day >= 27) setPlaying(false);
  }, [playing, day]);
  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (day >= 27) setDay(0);
    setPlaying(true);
  };

  const orchestrate = useOrchestrate();
  const busy = usePlanBusy();
  const replan = () => orchestrate.mutate(undefined, {
    onSuccess: (run) => {
      if (run.status === 'running') setParam('tab', 'negotiation');
      else showToast('The plan is up to date.', false);
    },
  });
  const forecast = useForecastOverride();
  const rainOn = windows.some((w) => w.kind === 'rain' && w.source === 'override');
  const simulateRain = () => forecast.mutate(
    { kind: 'rain', start_day: 12, end_day: 13, value: 70, label: 'Heavy rain, 14\u201315 Nov' },
    { onSuccess: () => { setDay(12); setParam('tab', 'risk'); } },
  );

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
        showToast(String(args.text ?? ''), false);
        break;
      default:
        break;
    }
  });

  // A link to a work that is not in this plan is dropped, with one note.
  const missing = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedWorkId) {
      missing.current = null;
      return;
    }
    if (!worksQ.isSuccess || views.some((v) => v.work.work_id === selectedWorkId)) return;
    if (missing.current === selectedWorkId) return;
    missing.current = selectedWorkId;
    setParam('work', null);
    showToast(`Work ${selectedWorkId} is not in this plan.`, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkId, worksQ.isSuccess, views]);

  const loading = planQ.isLoading || worksQ.isLoading;
  const failed = planQ.isError || worksQ.isError;
  const tryAgain = () => {
    if (planQ.isError) void planQ.refetch();
    if (worksQ.isError) void worksQ.refetch();
  };

  const mapViews = showOldWay ? oldViews : views;
  const counts = useMemo(() => mapLegendCounts(mapViews, day), [mapViews, day]);

  const tabItems = [
    { id: 'negotiation', label: 'Negotiation', count: messages.length },
    { id: 'works', label: 'Works', count: views.length },
    { id: 'risk', label: 'Risk', count: windows.length },
    { id: 'approvals', label: 'Approvals', count: pending.length },
  ];

  return (
    <div className={folded ? 'mm-app-cmd mm-app-cmd--folded' : 'mm-app-cmd'}>
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
                value={loading ? '\u2013' : now}
                unit={t.unit}
                compare={!loading && oldMetrics ? compareLabel(before) : undefined}
                delta={loading ? undefined : delta}
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
            onChange={(d) => { setPlaying(false); setDay(d); }}
            playing={playing}
            onPlay={togglePlay}
            valueLabel={dayLabel(day)}
            range="2–29 Nov"
            risks={windows.map((w) => ({ start: w.start_day, end: w.end_day + 1, kind: w.kind, label: w.label }))}
            tickLabel={(d) => WEEK_TICKS[d / 7] ?? ''}
          />
        </div>
        <span className="mm-app-cmd__divider" aria-hidden="true" />
        <Toggle checked={!showOldWay} onChange={(on) => setShowOldWay(!on)} off="Old way" on="MargaMitra" label="Compare with the old way" />
        <Button
          variant="ghost"
          icon="rain"
          onClick={simulateRain}
          disabled={rainOn || forecast.isPending || busy.running}
          title={rainOn ? 'Rain is already simulated' : undefined}
        >
          Simulate rain
        </Button>
        <Button variant="secondary" icon="refresh" onClick={replan}
          disabled={orchestrate.isPending || busy.running || busy.waiting}
          title={busy.running ? 'The scheduler is working on a plan' : busy.waiting ? 'Approve or reject the waiting plan first' : undefined}
        >
          Re-plan
        </Button>
      </div>

      <aside className={folded ? 'mm-app-cmd__panel mm-app-cmd__panel--folded' : 'mm-app-cmd__panel'}>
        <div className="mm-app-cmd__handle">
          <Button variant="ghost" onClick={() => setFolded(!folded)}>{folded ? 'Show plan' : 'Hide plan'}</Button>
        </div>
        <section className="mm-folder mm-app-cmd__folder">
          <div className="mm-folder__tab"><Icon name="handshake" size={16} />Plan for 2–29 Nov</div>
          <div className="mm-folder__body mm-app-cmd__body">
            <Tabs items={tabItems} value={tab} onChange={(id) => setParam('tab', id)} label="Plan panel" />
            {failed ? (
              <Banner
                tone="danger"
                title="Could not load the plan"
                action={<Button variant="secondary" onClick={tryAgain}>Try again</Button>}
              >
                {errorText(planQ.error ?? worksQ.error)}
              </Banner>
            ) : loading ? (
              <Card><span className="mono" style={{ color: 'var(--ink-3)' }}>Loading{'\u2026'}</span></Card>
            ) : tab === 'negotiation' ? (
              <NegotiationTab onReview={() => setParam('tab', 'approvals')} />
            ) : tab === 'works' ? (
              <WorksTab onPick={(id) => mapRef.current?.fitWork(id)} />
            ) : tab === 'risk' ? (
              <RiskTab onReview={() => setParam('tab', 'approvals')} />
            ) : (
              <ApprovalsTab />
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

      <div className="mm-app-cmd__toast">
        {toast ? (
          <Toast
            icon="check"
            actionLabel={toast.view ? 'View changes' : undefined}
            onAction={() => { setParam('tab', 'approvals'); setToast(null); }}
          >
            {toast.text}
          </Toast>
        ) : null}
      </div>
    </div>
  );
}