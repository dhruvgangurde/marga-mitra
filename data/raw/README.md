# Data snapshots

Both files are committed so that nothing needs the internet at run time or in tests.
Only the two `--fetch` commands touch the network, and a person runs them.

## osm_surathkal.json

- **What it holds:** every road way (trunk, primary, secondary, tertiary, unclassified, residential, service)
  inside the box 12.996, 74.776, 13.024, 74.812, with its tags, node ids and coordinates.
- **Refresh it:** `python -m data.osm_import --fetch` (tries three public Overpass servers in turn).
- **When:** only if the roads must change. Then refresh `elevations.json` too, because segment ids change.
- **Source and licence:** Road data © OpenStreetMap contributors, available under the Open Database License (ODbL 1.0).

## elevations.json

- **What it holds:** one elevation in metres for the midpoint of every road segment, keyed by segment id
  (`S-0001` ...). The lowest 20% become the low-lying roads.
- **Refresh it:** `python -m data.elevation --fetch` (about 20 small requests; it retries when the service is busy).
- **When:** after every refresh of `osm_surathkal.json`.
- **Source and licence:** Elevations from the Open-Meteo elevation API (CC BY 4.0).

## Checks

`python -m data.check` proves that the demo story can still happen on the real roads: the demo roads and works, the old way's clashes, the shared trench, the procession, the simulated rain, the demo forecast, and what test cases 2 to 50 contain. A FAIL stops the demo story, so fix it before anything else. A WARN is only a note. Add `--table` to see every test case and `--web PATH` to check the web export.

## weather_cache.json

The last live forecast, kept for 3 hours and never committed. Delete it to force a fresh fetch.
