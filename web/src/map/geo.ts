import type { Feature, FeatureCollection, LineString, MultiLineString, Point, Polygon } from 'geojson';
import { dayDate } from '../api/format';
import type { Dept, RiskWindow, SegmentFeature, WorkView } from '../api/types';
import { token } from './tokens';

export type Coord = [number, number];
const M_PER_DEG = 111320; // 1° of latitude, in metres

export type SegmentIndex = Map<string, SegmentFeature>;

export function segmentIndex(segments: SegmentFeature[]): SegmentIndex {
  return new Map(segments.map((s) => [s.properties.segment_id, s]));
}

function overlap(a0: number, a1: number, b0: number, b1: number): boolean {
  return Math.max(a0, b0) <= Math.min(a1, b1);
}

// The works that touch the seven days starting at `day`.
export function shownViews(views: WorkView[], day: number): WorkView[] {
  return views.filter((v) => v.assignment && overlap(v.assignment.start_day, v.assignment.end_day, day, day + 6));
}

export function shownRisk(windows: RiskWindow[], day: number): RiskWindow[] {
  return windows.filter((w) => overlap(w.start_day, w.end_day, day, day + 6));
}

function isoDay(day: number): string {
  return dayDate(day).toISOString().slice(0, 10);
}

// The roads, with a flag for the ones that are protected on the shown day.
export function roadsData(segments: SegmentFeature[], day: number): FeatureCollection<LineString> {
  const today = isoDay(day);
  return {
    type: 'FeatureCollection',
    features: segments.map((s) => ({
      type: 'Feature',
      geometry: s.geometry,
      properties: {
        segment_id: s.properties.segment_id,
        road_class: s.properties.road_class,
        protected: Boolean(s.properties.protected_until && s.properties.protected_until >= today),
      },
    })),
  };
}

function lineOf(seg: SegmentFeature | undefined): Coord[] | null {
  return seg ? (seg.geometry.coordinates as Coord[]) : null;
}

export function workLines(views: WorkView[], segments: SegmentIndex, selectedId: string | null = null): FeatureCollection<MultiLineString> {
  const features: Feature<MultiLineString>[] = [];
  for (const v of views) {
    const lines = v.work.segment_ids.map((id) => lineOf(segments.get(id))).filter((l): l is Coord[] => l !== null);
    if (!lines.length) continue;
    const group = v.assignment?.shared_group ?? null;
    const other = group
      ? views.find((o) => o.work.work_id !== v.work.work_id && o.assignment?.shared_group === group && o.work.dept !== v.work.dept)
      : undefined;
    const properties: Record<string, unknown> = {
      work_id: v.work.work_id,
      dept: v.work.dept,
      color: token('--dept-' + v.work.dept),
      status: v.status,
      shared_group: group,
      faded: v.status === 'done' || v.status === 'verified',
      selected: v.work.work_id === selectedId,
    };
    if (other) properties.second_color = token('--dept-' + other.work.dept);
    features.push({ type: 'Feature', geometry: { type: 'MultiLineString', coordinates: lines }, properties });
  }
  return { type: 'FeatureCollection', features };
}

// A polygon `width` metres either side of a line, offset along the normal at each vertex.
export function corridor(coords: Coord[], width = 35): Polygon {
  const left: Coord[] = [];
  const right: Coord[] = [];
  coords.forEach(([lon, lat], i) => {
    const prev = coords[Math.max(0, i - 1)];
    const next = coords[Math.min(coords.length - 1, i + 1)];
    const mLon = M_PER_DEG * Math.cos((lat * Math.PI) / 180);
    const tx = (next[0] - prev[0]) * mLon;
    const ty = (next[1] - prev[1]) * M_PER_DEG;
    const len = Math.hypot(tx, ty) || 1;
    const nx = -ty / len;
    const ny = tx / len;
    left.push([lon + (nx * width) / mLon, lat + (ny * width) / M_PER_DEG]);
    right.push([lon - (nx * width) / mLon, lat - (ny * width) / M_PER_DEG]);
  });
  const ring = [...left, ...right.reverse()];
  ring.push(ring[0]);
  return { type: 'Polygon', coordinates: [ring] };
}

export function riskAreas(windows: RiskWindow[], segments: SegmentIndex): FeatureCollection<Polygon> {
  const features: Feature<Polygon>[] = [];
  for (const w of windows) {
    for (const id of w.segment_ids) {
      const line = lineOf(segments.get(id));
      if (!line) continue;
      features.push({ type: 'Feature', geometry: corridor(line, 35), properties: { kind: w.kind, label: w.label } });
    }
  }
  return { type: 'FeatureCollection', features };
}

// The point halfway along a line.
export function midpoint(coords: Coord[]): Coord {
  const mLon = M_PER_DEG * Math.cos((coords[0][1] * Math.PI) / 180);
  const lens = coords.slice(1).map((c, i) => Math.hypot((c[0] - coords[i][0]) * mLon, (c[1] - coords[i][1]) * M_PER_DEG));
  let half = lens.reduce((a, b) => a + b, 0) / 2;
  for (let i = 0; i < lens.length; i++) {
    if (half <= lens[i] || i === lens.length - 1) {
      const t = lens[i] ? Math.min(1, half / lens[i]) : 0;
      return [coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t, coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t];
    }
    half -= lens[i];
  }
  return coords[0];
}

// The same_road, order and protected_road rules from contracts/rules.py.
export function clashPoints(views: WorkView[], segments: SegmentIndex): FeatureCollection<Point> {
  const features: Feature<Point>[] = [];
  const live = views.filter((v) => v.assignment && !v.work.done);
  const add = (segmentId: string | undefined, kind: string, start: number, end: number) => {
    const line = lineOf(segmentId ? segments.get(segmentId) : undefined);
    if (!line) return;
    features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: midpoint(line) }, properties: { kind, start_day: start, end_day: end } });
  };

  for (let i = 0; i < live.length; i++) {
    for (let j = i + 1; j < live.length; j++) {
      const a = live[i];
      const b = live[j];
      const aa = a.assignment!;
      const ba = b.assignment!;
      const shared = a.work.segment_ids.find((id) => b.work.segment_ids.includes(id));
      if (!shared || (aa.shared_group && aa.shared_group === ba.shared_group)) continue;
      const aRoads = a.work.dept === 'roads';
      const bRoads = b.work.dept === 'roads';
      if (aRoads !== bRoads) {
        const [r, u] = aRoads ? [aa, ba] : [ba, aa];
        if (u.mode === 'open_cut' && u.end_day >= r.start_day) add(shared, 'order', r.start_day, Math.max(r.end_day, u.end_day));
        continue;
      }
      if (aa.mode === 'open_cut' && ba.mode === 'open_cut' && overlap(aa.start_day, aa.end_day, ba.start_day, ba.end_day)) {
        add(shared, 'same_road', Math.max(aa.start_day, ba.start_day), Math.min(aa.end_day, ba.end_day));
      }
    }
  }

  for (const v of live) {
    const a = v.assignment!;
    if (a.mode !== 'open_cut' || v.work.is_emergency) continue;
    const today = isoDay(a.start_day);
    const hit = v.work.segment_ids.find((id) => {
      const until = segments.get(id)?.properties.protected_until;
      return Boolean(until && until >= today);
    });
    if (hit) add(hit, 'protected_road', a.start_day, a.end_day);
  }
  return { type: 'FeatureCollection', features };
}

export function mapLegendCounts(views: WorkView[], day: number): Partial<Record<Dept, number>> {
  const counts: Partial<Record<Dept, number>> = {};
  for (const v of shownViews(views, day)) counts[v.work.dept] = (counts[v.work.dept] ?? 0) + 1;
  return counts;
}

// Every coordinate of a work, for fitting the camera.
export function workCoords(view: WorkView, segments: SegmentIndex): Coord[] {
  return view.work.segment_ids.flatMap((id) => lineOf(segments.get(id)) ?? []);
}