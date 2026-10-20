import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.tables import LedgerRow
from contracts.models import LedgerEntry, LedgerVerify

GENESIS = "0" * 64


def entry_hash(seq: int, ts: datetime, actor: str, action: str, entity: str, summary: str,
               payload: dict[str, Any], prev_hash: str) -> str:
    body = {"seq": seq, "ts": ts.astimezone(UTC).isoformat(), "actor": actor, "action": action, "entity": entity,
            "summary": summary, "payload": payload, "prev_hash": prev_hash}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _entry(r: LedgerRow) -> LedgerEntry:
    return LedgerEntry.model_validate(r, from_attributes=True)


def append(s: Session, actor: str, action: str, entity: str, summary: str, payload: dict[str, Any]) -> LedgerEntry:
    s.execute(text("SELECT pg_advisory_xact_lock(4242)"))  # one writer at a time, so the chain never forks
    last = s.scalars(select(LedgerRow).order_by(LedgerRow.seq.desc()).limit(1)).first()
    seq, prev = (last.seq + 1, last.hash) if last else (1, GENESIS)
    ts = datetime.now(UTC)
    row = LedgerRow(seq=seq, ts=ts, actor=actor, action=action, entity=entity, summary=summary, payload=payload,
                    prev_hash=prev, hash=entry_hash(seq, ts, actor, action, entity, summary, payload, prev))
    s.add(row)
    s.flush()
    return _entry(row)


def verify(s: Session) -> LedgerVerify:
    # populate_existing: check what is stored, not objects this session already holds
    rows = s.scalars(select(LedgerRow).order_by(LedgerRow.seq).execution_options(populate_existing=True)).all()
    prev = GENESIS
    for r in rows:
        good = entry_hash(r.seq, r.ts, r.actor, r.action, r.entity, r.summary, r.payload, r.prev_hash)
        if r.prev_hash != prev or r.hash != good:
            return LedgerVerify(ok=False, entries=len(rows), first_bad_seq=r.seq)
        prev = r.hash
    return LedgerVerify(ok=True, entries=len(rows))


def latest(s: Session, limit: int = 50, before_seq: int | None = None) -> list[LedgerEntry]:
    q = select(LedgerRow).order_by(LedgerRow.seq.desc()).limit(limit)
    if before_seq is not None:
        q = q.where(LedgerRow.seq < before_seq)
    return [_entry(r) for r in s.scalars(q)]
