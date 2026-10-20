const EARTH_RADIUS_M = 6371000;
const rad = (deg: number) => (deg * Math.PI) / 180;

export function metresBetween(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a));
}

// Distance from the origin to the segment a–b, all in metres.
function toSegment([ax, ay]: [number, number], [bx, by]: [number, number]): number {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2));
  return Math.hypot(ax + t * dx, ay + t * dy);
}

// shortcut: flat projection, fine within a few kilometres; the server makes the real place check.
export function metresToLine(lat: number, lon: number, line: [number, number][]): number {
  const kx = Math.cos(rad(lat)) * 111320;
  const points = line.map(([x, y]): [number, number] => [(x - lon) * kx, (y - lat) * 110540]);
  if (points.length === 1) return Math.hypot(points[0][0], points[0][1]);
  let best = Infinity;
  for (let i = 1; i < points.length; i++) best = Math.min(best, toSegment(points[i - 1], points[i]));
  return best;
}
