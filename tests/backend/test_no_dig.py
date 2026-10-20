from datetime import date

from backend.app import store
from backend.app.db import session

PLANNED = {"name": "Test Road", "protected_until": "2029-11-12", "why": "From the planned resurfacing R-001"}


def _protect(segment_id: str, until: date) -> None:
    with session() as s:
        scenario = store.get_scenario(s, 1)
        seg = next(g for g in scenario.segments if g.segment_id == segment_id)
        seg.protected_until = until
        store.put_scenario(s, scenario)


def test_planned_resurfacing_protects_its_roads(client):
    # P-OLD-1 is active; R-001 ends on day 11 = 13 Nov 2026, then 1,095 days
    assert client.get("/no-dig").json() == [{"segment_id": sid, **PLANNED} for sid in ("S-0001", "S-0002", "S-0003")]


def test_one_entry_per_segment_with_the_later_date(client):
    _protect("S-0003", date(2029, 1, 1))
    entries = [e for e in client.get("/no-dig").json() if e["segment_id"] == "S-0003"]
    assert entries == [{"segment_id": "S-0003", **PLANNED}]

    _protect("S-0003", date(2030, 1, 1))
    entries = [e for e in client.get("/no-dig").json() if e["segment_id"] == "S-0003"]
    assert entries == [{"segment_id": "S-0003", "name": "Test Road", "protected_until": "2030-01-01",
                        "why": "Resurfaced recently"}]
