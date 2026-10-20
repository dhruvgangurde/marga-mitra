import asyncio
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from backend.app import storage, store
from backend.app.db import session
from backend.app.ids import next_id
from backend.app.routers.city import DEPT_NAMES
from backend.app.verify.exif import INDIA, read_photo_facts
from backend.app.verify.phash import fingerprint
from contracts.models import Evidence, Work

router = APIRouter(tags=["photos"])


def _work_or_404(seed: int, work_id: str) -> Work:
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
    work = await asyncio.to_thread(_work_or_404, seed, work_id)
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


def _list(seed: int, work_id: str) -> list[Evidence]:
    _work_or_404(seed, work_id)
    with session() as s:
        return store.list_evidence(s, seed, work_id)


@router.get("/works/{work_id}/evidence")
def list_evidence(request: Request, work_id: str) -> list[Evidence]:
    return _list(request.app.state.seed, work_id)
