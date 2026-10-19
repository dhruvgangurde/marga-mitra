
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

QUERY = (
    '[out:json][timeout:90];'
    'way["highway"~"^(trunk|primary|secondary|tertiary|unclassified|residential|service)$"]'
    "(12.996,74.776,13.024,74.812);"
    "out geom;"
)

SNAPSHOT = Path(__file__).resolve().parent / "raw" / "osm_surathkal.json"

USER_AGENT = "MargaMitra/0.1 (ChronoForge 2026, NITK Surathkal)"


@dataclass(frozen=True)
class Way:
    id: int
    tags: dict[str, str]
    nodes: list[int]
    coords: list[tuple[float, float]]  # (lon, lat)


def fetch() -> None:
    """Download roads and save a local snapshot. Run manually, never in tests."""

    response = None

    for url in OVERPASS_URLS:
        try:
            response = httpx.post(
                url,
                data={"data": QUERY},
                headers={"User-Agent": USER_AGENT},
                timeout=120,
            )
            response.raise_for_status()
            print(f"Got the roads from {url}")
            break

        except httpx.HTTPError as err:
            print(f"{url} failed: {err}")
            response = None

    if response is None:
        raise SystemExit(
            "All servers failed. Wait a few minutes and run --fetch again."
        )

    data = response.json()

    ways = []

    for el in data.get("elements", []):
        if el.get("type") != "way" or not el.get("geometry"):
            continue

        ways.append(
            {
                "id": el["id"],
                "tags": el.get("tags", {}),
                "nodes": el.get("nodes", []),
                "coords": [
                    [
                        round(point["lon"], 7),
                        round(point["lat"], 7),
                    ]
                    for point in el["geometry"]
                ],
            }
        )

    ways.sort(key=lambda way: way["id"])

    snapshot_data = {
        "query": QUERY,
        "fetched_at": datetime.now(UTC).isoformat(),
        "ways": ways,
    }

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)

    SNAPSHOT.write_text(
        json.dumps(
            snapshot_data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(f"Wrote {len(ways)} ways to {SNAPSHOT}")


def load_ways() -> list[Way]:
    """Load the saved road snapshot without making network requests."""

    if not SNAPSHOT.exists():
        raise FileNotFoundError(
            f"Snapshot not found at {SNAPSHOT}. "
            "Run: python -m data.osm_import --fetch"
        )

    raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    return [
        Way(
            id=way["id"],
            tags=way["tags"],
            nodes=list(way["nodes"]),
            coords=[
                (float(lon), float(lat))
                for lon, lat in way["coords"]
            ],
        )
        for way in raw["ways"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenStreetMap roads snapshot for Surathkal"
    )

    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download roads from Overpass (requires internet)",
    )

    args = parser.parse_args()

    if args.fetch:
        fetch()
    else:
        ways = load_ways()
        print(f"{len(ways)} ways in the snapshot")


if __name__ == "__main__":
    main()
