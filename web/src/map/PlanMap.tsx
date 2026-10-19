import 'maplibre-gl/dist/maplibre-gl.css';
import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { GeoJSONSource } from 'maplibre-gl';
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { dayRange, workStatusBadge } from '../api/format';
import type { RiskWindow, SegmentCollection, WorkView } from '../api/types';
import { DeptChip, Icon, StatusBadge } from '../ui';
import { clashPoints, midpoint, riskAreas, roadsData, segmentIndex, shownRisk, shownViews, workCoords, workLines } from './geo';
import type { Coord } from './geo';
import { addPatterns, buildStyle } from './style';

export interface PlanMapHandle {
  fitWork: (workId: string) => void;
  fitAll: () => void;
}

export interface PlanMapProps {
  views: WorkView[];
  segments: SegmentCollection | undefined;
  riskWindows: RiskWindow[];
  day: number;
  selectedWorkId: string | null;
  onSelectWork: (workId: string | null) => void;
}

// Vite can't find the map's worker by itself, so point it there.
maplibregl.setWorkerUrl(workerUrl);

const CENTER: [number, number] = [74.794, 13.01];
const PADDING = { top: 140, right: 452, bottom: 210, left: 80 };
const HIT_LAYERS = ['works', 'works-selected'];

function reducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function setData(map: maplibregl.Map, id: string, data: GeoJSON.FeatureCollection): void {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data);
}

export const PlanMap = forwardRef<PlanMapHandle, PlanMapProps>(function PlanMap(
  { views, segments, riskWindows, day, selectedWorkId, onSelectWork },
  ref,
) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  const index = useMemo(() => segmentIndex(segments?.features ?? []), [segments]);
  const shown = useMemo(() => shownViews(views, day), [views, day]);
  const live = useRef({ shown, index, onSelectWork });
  live.current = { shown, index, onSelectWork };

  useImperativeHandle(ref, () => ({
    fitWork(workId) {
      const map = mapRef.current;
      const view = views.find((v) => v.work.work_id === workId);
      if (!map || !view) return;
      fit(map, workCoords(view, index));
    },
    fitAll() {
      const map = mapRef.current;
      if (!map) return;
      const coords = shown.flatMap((v) => workCoords(v, index));
      fit(map, coords.length ? coords : (segments?.features ?? []).flatMap((f) => f.geometry.coordinates as Coord[]));
    },
  }), [views, shown, index, segments]);

  // Make the map once; remove it when the screen goes away.
  useEffect(() => {
    if (!box.current) return undefined;
    const map = new maplibregl.Map({
      container: box.current,
      style: buildStyle(),
      center: CENTER,
      zoom: 14.2,
      minZoom: 13,
      maxZoom: 17,
      maxBounds: [[74.77, 12.99], [74.818, 13.03]],
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: false,
    });
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new maplibregl.AttributionControl({ customAttribution: '© OpenStreetMap contributors' }), 'bottom-right');
    map.on('load', () => {
      addPatterns(map);
      setReady(true);
    });

    const hit = (point: maplibregl.Point) => {
      const found = map.queryRenderedFeatures(
        [[point.x - 8, point.y - 8], [point.x + 8, point.y + 8]],
        { layers: HIT_LAYERS },
      );
      return found.length ? String(found[0].properties?.work_id) : null;
    };
    map.on('mousemove', (e) => {
      const id = hit(e.point);
      map.getCanvas().style.cursor = id ? 'pointer' : '';
      setHover(id ? { id, x: e.point.x, y: e.point.y } : null);
    });
    map.on('mouseout', () => setHover(null));
    map.on('click', (e) => live.current.onSelectWork(hit(e.point)));

    mapRef.current = map;
    return () => {
      markers.current.forEach((m) => m.remove());
      markers.current = [];
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, []);

  // Data changes go through setData.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, 'roads', roadsData(segments?.features ?? [], day));
  }, [ready, segments, day]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, 'works', workLines(shown, index, selectedWorkId));
    setData(map, 'clashes', clashPoints(shown, index));
  }, [ready, shown, index, selectedWorkId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, 'risk', riskAreas(shownRisk(riskWindows, day), index));
  }, [ready, riskWindows, day, index]);

  // Emergency works get a pulsing siren marker.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return undefined;
    const made = shown
      .filter((v) => v.work.is_emergency || v.status === 'emergency')
      .flatMap((v) => {
        const first = v.work.segment_ids.map((id) => index.get(id)).find(Boolean);
        if (!first) return [];
        const el = document.createElement('div');
        el.className = 'mm-app-marker';
        el.innerHTML = '<span class="mm-live__dot mm-app-marker__pulse"></span>' + renderToStaticMarkup(<Icon name="siren" size={18} />);
        return [new maplibregl.Marker({ element: el }).setLngLat(midpoint(first.geometry.coordinates as Coord[])).addTo(map)];
      });
    markers.current = made;
    return () => made.forEach((m) => m.remove());
  }, [ready, shown, index]);

  const hovered = hover ? views.find((v) => v.work.work_id === hover.id) : undefined;
  const badge = hovered ? workStatusBadge(hovered.status) : null;
  const width = box.current?.clientWidth ?? 0;
  const flip = hover ? hover.x > width * 0.6 : false;

  return (
    <div className="mm-app-map">
      <div ref={box} className="mm-app-map__canvas" />
      {hover && hovered && badge && hovered.assignment ? (
        <div
          className="mm-app-maphover"
          style={{ left: flip ? hover.x - 12 : hover.x + 12, top: hover.y + 12, transform: flip ? 'translateX(-100%)' : undefined }}
        >
          <span className="body-strong">{hovered.work.title}</span>
          <DeptChip dept={hovered.work.dept} />
          <span className="mono">{dayRange(hovered.assignment.start_day, hovered.assignment.end_day)}</span>
          <StatusBadge status={badge.status}>{badge.label}</StatusBadge>
        </div>
      ) : null}
    </div>
  );
});

function fit(map: maplibregl.Map, coords: Coord[]): void {
  if (!coords.length) return;
  const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
  map.fitBounds(bounds, { padding: PADDING, duration: reducedMotion() ? 0 : 600, maxZoom: 16 });
}