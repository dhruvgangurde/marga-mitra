from datetime import UTC, datetime

from sqlalchemy import text

from backend.app import ledger
from backend.app.db import session


def test_entry_hash_is_stable():
    ts = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
    h = ledger.entry_hash(1, ts, "rules", "plan.approved", "plan:P-0001", "Approved", {"a": 1, "b": 2}, ledger.GENESIS)
    assert h == ledger.entry_hash(1, ts, "rules", "plan.approved", "plan:P-0001", "Approved", {"b": 2, "a": 1}, ledger.GENESIS)
    assert len(h) == 64 and int(h, 16) >= 0
    assert h != ledger.entry_hash(1, ts, "rules", "plan.approved", "plan:P-0001", "Changed", {"a": 1, "b": 2}, ledger.GENESIS)


def _append_three() -> list:
    with session() as s:
        return [ledger.append(s, "system", "test.added", f"test:{i}", f"Entry {i}", {"i": i}) for i in (1, 2, 3)]


def test_append_chains_entries(db):
    entries = _append_three()
    assert [e.seq for e in entries] == [1, 2, 3]
    assert entries[0].prev_hash == ledger.GENESIS
    assert entries[1].prev_hash == entries[0].hash
    assert entries[2].prev_hash == entries[1].hash


def test_verify_finds_the_changed_entry(db):
    _append_three()
    with session() as s:
        assert ledger.verify(s).model_dump() == {"ok": True, "entries": 3, "first_bad_seq": None}
        s.execute(text("UPDATE ledger SET summary = 'Changed' WHERE seq = 2"))
        assert ledger.verify(s).model_dump() == {"ok": False, "entries": 3, "first_bad_seq": 2}


def test_payload_round_trip(db):
    with session() as s:
        ledger.append(s, "forecast", "forecast.override", "risk:OV-1", "Heavy rain",
                      {"window": {"value": 70.0, "days": [12, 13], "deposit": "₹2,40,000"}, "z": None})
    with session() as s:
        assert ledger.verify(s).ok
        assert ledger.latest(s)[0].payload["window"]["value"] == 70.0
