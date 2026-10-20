from fastapi import APIRouter, Query

from backend.app import ledger
from backend.app.db import session
from contracts.models import LedgerEntry, LedgerVerify

router = APIRouter(tags=["record"])


@router.get("/ledger")
def entries(limit: int = Query(50, ge=1, le=500), before_seq: int | None = None) -> list[LedgerEntry]:
    with session() as s:
        return ledger.latest(s, limit, before_seq)


@router.get("/ledger/verify")
def verify() -> LedgerVerify:
    with session() as s:
        return ledger.verify(s)
