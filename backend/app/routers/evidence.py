import asyncio
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile

from backend.app import storage, store
from backend.app.auditor import safe_audit
from backend.app.db import session
from backend.app.ids import next_id
from backend.app.routers.city import DEPT_NAMES
from backend.app.verify.decide import decide
from backend.app.verify.exif import INDIA, read_photo_facts
from backend.app.verify.phash import fingerprint
from backend.app.verify.vision import repair_check
from contracts.costs import inr
from contracts.models import Evidence, Verification, VerificationCheck, Work, WsEvent

router = APIRouter(tags=["photos"])


def work_or_404(seed: int, work_id: str) -> Work:
    with session() as s:
        scenario = store.get_scenario(s, seed)
    work = next((w for w in scenario.works if w.work_id == work_id), None) if scenario else None
    if work is None:
        raise HTTPException(404, "Unknown work.")
    return work


def _facts(data: bytes, lat: float | None, lon: float | None,
           taken_at: datetime | None) -> tuple[float | None, float | None, datetime | None, str, str]:
    """The photo's own place and time first; the phone's only fill what the photo lacks."""
    p_lat, p_lon, p_taken = read_photo_facts(data)
    if p_lat is not None and p_lon is not None:
        lat, lon, place_from = p_lat, p_lon, "photo"
    elif lat is not None and lon is not None:
        place_from = "phone"
    else:
        lat, lon, place_from = None, None, "none"
    if p_taken is not None:
        taken_at, time_from = p_taken, "photo"
    elif taken_at is not None:
        taken_at, time_from = taken_at if taken_at.tzinfo else taken_at.replace(tzinfo=INDIA), "phone"
    else:
        time_from = "none"
    return lat, lon, taken_at, place_from, time_from


def _save(seed: int, work_id: str, kind: str, data: bytes, ext: str, lat: float | None, lon: float | None,
          taken_at: datetime | None) -> Evidence:
    lat, lon, taken_at, place_from, time_from = _facts(data, lat, lon, taken_at)
    phash = fingerprint(data)
    with session() as s:
        evidence_id = next_id(s, "E")
        rel = storage.save_photo(work_id, evidence_id, data, ext)
        ev = Evidence(evidence_id=evidence_id, work_id=work_id, kind=kind, file_url=storage.file_url(rel), lat=lat,
                      lon=lon, taken_at=taken_at, phash=phash, uploaded_at=store.db_now(s))
        store.add_evidence(s, seed, ev, rel, place_from, time_from)
    return ev


@router.post("/works/{work_id}/evidence", status_code=201)
async def add_evidence(
    request: Request,
    work_id: str,
    kind: Annotated[Literal["before", "after", "citizen"], Form()],
    photo: Annotated[UploadFile, File()],
    lat: Annotated[float | None, Form(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Form(ge=-180, le=180)] = None,
    taken_at: Annotated[datetime | None, Form()] = None,
) -> Evidence:
    seed = request.app.state.seed
    work = await asyncio.to_thread(work_or_404, seed, work_id)
    data = await photo.read(storage.MAX_PHOTO_BYTES + 1)
    try:
        ext = storage.check_photo(data)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    ev = await asyncio.to_thread(_save, seed, work_id, kind, data, ext, lat, lon, taken_at)
    if kind == "citizen":
        actor, summary = "resident", f"A resident added a photo for {work_id}"
    else:
        actor, summary = work.dept.value, f"{DEPT_NAMES[work.dept.value]} crew added the {kind} photo for {work_id}"
    await request.app.state.wiring.deps.ledger_append(actor, "evidence.added", f"work:{work_id}", summary,
                                                      ev.model_dump(mode="json"))
    return ev


def newest_pair(seed: int, work_id: str) -> tuple[Evidence, Evidence] | None:
    """The newest before and after photo of a work, or None while one is missing."""
    with session() as s:
        newest = {e.kind: e for e in store.list_evidence(s, seed, work_id)}  # oldest first, so the newest wins
    return (newest["before"], newest["after"]) if {"before", "after"} <= newest.keys() else None


def _photo_bytes(ev: Evidence) -> bytes | None:
    with session() as s:
        rel = store.evidence_path(s, ev.evidence_id)
    path = storage.resolve(rel) if rel else None
    return path.read_bytes() if path else None


def _decide_and_save(seed: int, work_id: str, repair: VerificationCheck | None) -> Verification:
    with session() as s:
        scenario = store.get_scenario(s, seed)
        plan = store.active_plan(s, seed)
        work = next(w for w in scenario.works if w.work_id == work_id)
        v = decide(work=work, assignment=next((a for a in plan.assignments if a.work_id == work_id), None) if plan else None,
                   evidence=store.list_evidence(s, seed, work_id), scenario=scenario,
                   others=store.evidence_of_others(s, seed, work_id), repair=repair,
                   answers=store.confirmations(s, seed, work_id), verification_id=next_id(s, "V"), now=store.db_now(s))
        store.add_verification(s, seed, v)
    return v


def _summary(v: Verification) -> str:
    wid = v.work_id
    if v.result == "verified":
        return f"Repair verified for {wid}: every check passed"
    if v.result == "held":
        return f"Money held for {wid}: {next(c for c in v.checks if c.status == 'fail').detail}"
    if v.result == "inspect":
        # a resident's pending answer alone never calls an inspector, so it is not the reason given
        why = next(c for c in v.checks if c.status == "warn" or (c.status == "pending" and c.name != "resident"))
        return f"{wid} needs an inspector: {why.detail}"
    return f"{wid} waits for a resident to confirm"


async def verify_work(app: FastAPI, seed: int, work_id: str) -> Verification:
    """Run the six checks on a work's newest photos, store the decision, record it and send it live."""
    pair = await asyncio.to_thread(newest_pair, seed, work_id)
    if pair is None:
        raise HTTPException(422, "Add the before and after photos first.")
    before, after = [await asyncio.to_thread(_photo_bytes, ev) for ev in pair]
    # a photo file that is gone leaves the repair to a person
    repair = await repair_check(before, after) if before and after else None
    v = await asyncio.to_thread(_decide_and_save, seed, work_id, repair)
    deps = app.state.wiring.deps
    entity, money = f"work:{work_id}", inr(v.deposit_inr)
    await deps.ledger_append("photo_check", "verification.decided", entity, _summary(v), v.model_dump(mode="json"))
    ids = {"verification_id": v.verification_id, "deposit_inr": v.deposit_inr}
    if v.result == "verified":
        await deps.ledger_append("photo_check", "deposit.released", entity,
                                 f"{money} released to the contractor for {work_id}", ids)
    elif v.result == "held":
        await deps.ledger_append("photo_check", "deposit.held", entity,
                                 f"{money} held for {work_id}; an inspector is called", ids)
    await deps.emit(WsEvent(type="verification.result", data=v.model_dump(mode="json"), ts=datetime.now(UTC)))
    await safe_audit(app)
    return v


@router.post("/works/{work_id}/verify")
async def verify(request: Request, work_id: str) -> Verification:
    seed = request.app.state.seed
    await asyncio.to_thread(work_or_404, seed, work_id)
    return await verify_work(request.app, seed, work_id)


def _latest(seed: int, work_id: str) -> Verification:
    work_or_404(seed, work_id)
    with session() as s:
        v = store.latest_verification(s, seed, work_id)
    if v is None:
        raise HTTPException(404, "No check yet.")
    return v


@router.get("/works/{work_id}/verification")
def latest_verification(request: Request, work_id: str) -> Verification:
    return _latest(request.app.state.seed, work_id)


def _list(seed: int, work_id: str) -> list[Evidence]:
    work_or_404(seed, work_id)
    with session() as s:
        return store.list_evidence(s, seed, work_id)


@router.get("/works/{work_id}/evidence")
def list_evidence(request: Request, work_id: str) -> list[Evidence]:
    return _list(request.app.state.seed, work_id)
