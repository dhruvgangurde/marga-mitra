"""Cut the OpenStreetMap roads into segments of at most 300 m."""

from __future__ import annotations

import math
import re
from bisect import bisect_right
from collections import defaultdict

from contracts.models import RoadClass, Segment
from data.osm_import import Way, load_ways

MAP_BOUNDS = (74.770, 12.990, 74.818, 13.030)  # minLon, minLat, maxLon, maxLat
MAX_LEN_M = 300.0
EARTH_RADIUS_M = 6_371_000

LANES_BY_CLASS = {
    RoadClass.trunk: 4,
    RoadClass.primary: 4,
    RoadClass.secondary: 2,
    RoadClass.tertiary: 2,
    RoadClass.unclassified: 1,
    RoadClass.residential: 1,
    RoadClass.service: 1,
}
TRAFFIC_WEIGHT = {
    RoadClass.trunk: 5.0,
    RoadClass.primary: 4.0,
    RoadClass.secondary: 3.0,
    RoadClass.tertiary: 2.0,
    RoadClass.unclassified: 1.0,
    RoadClass.residential: 1.0,
    RoadClass.service: 0.5,
}

Point = tuple[float, float]  # (lon, lat)

_CACHE: tuple[Segment, ...] | None = None


def haversine_m(a: Point, b: Point) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def line_length_m(coords: list[Point]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(coords, coords[1:], strict=False))


def lanes_for(tags: dict[str, str], road_class: RoadClass) -> int:
    """First whole number in the "lanes" tag, clamped to 1..6; else the class default."""
    match = re.search(r"\d+", tags.get("lanes", ""))
    if match:
        return max(1, min(6, int(match.group())))
    return LANES_BY_CLASS[road_class]


def _inside(coords: list[Point]) -> bool:
    lon = (coords[0][0] + coords[-1][0]) / 2
    lat = (coords[0][1] + coords[-1][1]) / 2
    min_lon, min_lat, max_lon, max_lat = MAP_BOUNDS
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _split_long(coords: list[Point]) -> list[list[Point]]:
    """Cut a line into n = ceil(length / 300) parts of equal length."""
    cum = [0.0]
    for a, b in zip(coords, coords[1:], strict=False):
        cum.append(cum[-1] + haversine_m(a, b))
    total = cum[-1]
    n = math.ceil(total / MAX_LEN_M)
    if n <= 1:
        return [coords]

    def point_at(d: float) -> Point:
        i = min(max(bisect_right(cum, d) - 1, 0), len(coords) - 2)
        span = cum[i + 1] - cum[i]
        t = 0.0 if span == 0 else (d - cum[i]) / span
        (x1, y1), (x2, y2) = coords[i], coords[i + 1]
        return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)

    cuts = [coords[0]] + [point_at(total * k / n) for k in range(1, n)] + [coords[-1]]
    parts = []
    for k in range(n):
        d0, d1 = total * k / n, total * (k + 1) / n
        inner = [coords[i] for i in range(1, len(coords) - 1) if d0 < cum[i] < d1]
        parts.append([cuts[k], *inner, cuts[k + 1]])
    return parts


def _pieces(way: Way, shared: set[int]) -> list[list[Point]]:
    """Cut a way at every inner node that another way also uses."""
    last = len(way.nodes) - 1
    cut_at = [0] + [i for i in range(1, last) if way.nodes[i] in shared] + [last]
    return [way.coords[a : b + 1] for a, b in zip(cut_at, cut_at[1:], strict=False)]


def _build() -> tuple[Segment, ...]:
    ways = sorted(load_ways(), key=lambda w: w.id)
    users: dict[int, set[int]] = defaultdict(set)
    for way in ways:
        for node in way.nodes:
            users[node].add(way.id)
    shared = {node for node, ids in users.items() if len(ids) >= 2}

    made: list[tuple[Way, list[Point]]] = []
    for way in ways:
        for piece in _pieces(way, shared):
            for part in _split_long(piece):
                part = [(round(x, 6), round(y, 6)) for x, y in part]
                if line_length_m(part) < 1.0 or not _inside(part):
                    continue
                made.append((way, part))

    ends: dict[Point, list[str]] = defaultdict(list)
    ids = [f"S-{i:04d}" for i in range(1, len(made) + 1)]
    for sid, (_, part) in zip(ids, made, strict=True):
        for end in {part[0], part[-1]}:
            ends[end].append(sid)

    segments = []
    for sid, (way, part) in zip(ids, made, strict=True):
        road_class = RoadClass(way.tags["highway"])
        near = {o for end in (part[0], part[-1]) for o in ends[end]} - {sid}
        segments.append(
            Segment(
                segment_id=sid,
                osm_way_id=way.id,
                name=way.tags.get("name") or way.tags.get("ref") or None,
                road_class=road_class,
                length_m=round(line_length_m(part), 1),
                lanes=lanes_for(way.tags, road_class),
                traffic_weight=TRAFFIC_WEIGHT[road_class],
                neighbors=sorted(near),
                coords=part,
            )
        )
    return tuple(segments)


def build_segments() -> list[Segment]:
    """Segments without elevation. Fresh copies every call."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _build()
    return [s.model_copy(deep=True) for s in _CACHE]


def load_segments() -> list[Segment]:
    from data.elevation import apply_elevation

    return apply_elevation(build_segments())