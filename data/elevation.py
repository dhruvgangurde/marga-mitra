# The elevation file is keyed by segment id, so re-run the fetch whenever osm_surathkal.json changes.
"""Elevations for the road segments, and the low-lying roads.

Only `--fetch` touches the network, and only a person runs it.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from contracts import costs
from contracts.models import Segment

URL = "https://api.open-meteo.com/v1/elevation"
ELEVATIONS = Path(__file__).resolve().parent / "raw" / "elevations.json"
USER_AGENT = "MargaMitra/0.1 (ChronoForge 2026, NITK Surathkal)"
BATCH = 50


def midpoint(segment: Segment) -> tuple[float, float]:
    (lon1, lat1), (lon2, lat2) = segment.coords[0], segment.coords[-1]
    return ((lon1 + lon2) / 2, (lat1 + lat2) / 2)


def _get(lats: list[float], lons: list[float]) -> list[float]:
    params = {
        "latitude": ",".join(f"{v:.6f}" for v in lats),
        "longitude": ",".join(f"{v:.6f}" for v in lons),
    }
    for attempt in range(6):
        try:
            response = httpx.get(URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
            if response.status_code == 429 or response.status_code >= 500:
                raise httpx.HTTPError(f"status {response.status_code}")
            response.raise_for_status()
            return response.json()["elevation"]
        except httpx.HTTPError as err:
            print(f"  retry {attempt + 1}/6 ({err})")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("the elevation service kept failing; try again in a few minutes")


def fetch(segments: list[Segment]) -> None:
    """Download one elevation per segment midpoint. Run by a person, never by tests."""
    found: dict[str, float] = {}
    for start in range(0, len(segments), BATCH):
        batch = segments[start : start + BATCH]
        points = [midpoint(s) for s in batch]
        values = _get([p[1] for p in points], [p[0] for p in points])
        for segment, value in zip(batch, values, strict=True):
            found[segment.segment_id] = round(float(value), 1)
        print(f"  {min(start + BATCH, len(segments))} / {len(segments)}")
        time.sleep(1)
    out = {
        "source": "Open-Meteo elevation API",
        "fetched_at": datetime.now(UTC).isoformat(),
        "elevations": found,
    }
    ELEVATIONS.parent.mkdir(parents=True, exist_ok=True)
    ELEVATIONS.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(found)} elevations to {ELEVATIONS}")


def apply_elevation(segments: list[Segment]) -> list[Segment]:
    """New segments with elevation_m set and the lowest percentile marked low_lying."""
    result = [s.model_copy(deep=True) for s in segments]
    if not ELEVATIONS.exists():
        return result
    elevations = json.loads(ELEVATIONS.read_text(encoding="utf-8"))["elevations"]
    for s in result:
        s.elevation_m = elevations.get(s.segment_id)
    known = sorted((s for s in result if s.elevation_m is not None), key=lambda s: (s.elevation_m, s.segment_id))
    percentile = costs.policy()["risk"]["low_lying_percentile"]
    for s in known[: round(len(known) * percentile / 100)]:
        s.low_lying = True
    return result


def main() -> None:
    from data.segments import build_segments

    parser = argparse.ArgumentParser(description="Elevations for the road segments")
    parser.add_argument("--fetch", action="store_true", help="download the elevations (needs internet)")
    args = parser.parse_args()
    if args.fetch:
        fetch(build_segments())
        return
    segments = apply_elevation(build_segments())
    have = sum(s.elevation_m is not None for s in segments)
    low = sum(s.low_lying for s in segments)
    print(f"{have} of {len(segments)} segments have an elevation; {low} are low-lying")


if __name__ == "__main__":
    main()
