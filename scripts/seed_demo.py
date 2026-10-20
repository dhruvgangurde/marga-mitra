"""Replay the demo's morning on the current database. Run: python -m scripts.seed_demo [--reset]"""
import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.app import store
from backend.app.config import get_settings
from backend.app.db import engine, init_db, session
from backend.app.main import app
from backend.app.tables import Base, LedgerRow
from scripts.make_demo_photos import OUT, site_point

PHOTOS = OUT / "photos.json"
CHECKPOINT_TABLES = ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]
RUN_WAIT_S = 90


class StepFailed(Exception):
    pass


def _call(c: TestClient, method: str, url: str, **kw: Any) -> Any:
    r = c.request(method, url, **kw)
    if not r.is_success:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type") == "application/json" else r.text
        raise StepFailed(f"{method} {url} answered {r.status_code}: {detail}")
    return r.json()


def _already_seeded() -> bool:
    with session() as s:
        return s.scalar(select(LedgerRow.seq).where(LedgerRow.action == "emergency.reported").limit(1)) is not None


def _reset(base: Path) -> None:
    with engine().begin() as c:
        found = [t for t in CHECKPOINT_TABLES if c.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{t}"}).scalar()]
        c.execute(text(f"TRUNCATE {', '.join([*Base.metadata.tables, *found])} RESTART IDENTITY CASCADE"))
    if base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()


def _wait_for_approval(c: TestClient, run_id: str) -> dict:
    deadline = time.monotonic() + RUN_WAIT_S
    while time.monotonic() < deadline:
        run = _call(c, "GET", f"/runs/{run_id}")
        if run["status"] == "waiting_approval":
            return run
        if run["status"] != "running":
            raise StepFailed(f"Re-plan {run_id} ended as {run['status']}: {run['note']}")
        time.sleep(0.5)
    raise StepFailed(f"Re-plan {run_id} did not reach approval in {RUN_WAIT_S} seconds.")


def _morning(c: TestClient) -> None:
    with session() as s:
        scenario = store.get_scenario(s, 1)
    lat, lon = site_point(scenario, "W-118", 5)
    report = _call(c, "POST", "/reports/emergency", data={
        "category": "water", "lat": str(lat), "lon": str(lon), "note": "Water is running across the road."})
    wid = report["work_id"]
    print(f"A resident reports a burst water pipe near W-118: emergency dig {wid}.")

    with session() as s:
        run_id = store.newest_run_id(s, 1)
    run = _wait_for_approval(c, run_id)
    print(f"Re-plan {run_id} made plan {run['plan_id']} and waits for approval {run['approval_id']}.")

    # Rejected, not approved: the old way must stay the starting plan, so the live re-plan still has every clash to solve.
    _call(c, "POST", f"/approvals/{run['approval_id']}", json={
        "decision": "reject", "by": "ward_engineer",
        "reason": f"Emergency dig {wid} is fine. Every road is re-planned together at 10:00."})
    print(f"The ward engineer reviewed {wid} and kept the old way for now.")

    old = _call(c, "POST", "/plan/naive")
    print(f"Old way {old['plan_id']} saved with {len(old['assignments'])} works.")

    shots = json.loads(PHOTOS.read_text(encoding="utf-8"))
    for shot in shots:
        form = {"kind": shot["kind"]}
        if shot["facts"] == "phone":
            form |= {"lat": str(shot["lat"]), "lon": str(shot["lon"]), "taken_at": shot["taken_at"]}
        data = (OUT / shot["file"]).read_bytes()
        _call(c, "POST", f"/works/{shot['work_id']}/evidence", data=form,
              files={"photo": (shot["file"], data, "image/jpeg")})
    print(f"Added {len(shots)} crew photos.")

    results = [f"{w}: {_call(c, 'POST', f'/works/{w}/verify')['result']}" for w in ("T-230", "P-125", "W-104")]
    print(f"Photo checks: {', '.join(results)}.")

    _call(c, "POST", "/reports/confirmation", json={"work_id": "D-415", "answer": "yes", "problems": []})
    print(f"A resident says D-415 is restored: {_call(c, 'GET', '/works/D-415/verification')['result']}.")

    check = _call(c, "GET", "/ledger/verify")
    print(f"Record check: {'passes' if check['ok'] else 'fails at #' + str(check['first_bad_seq'])} "
          f"({check['entries']} entries).")
    for flag in _call(c, "GET", "/auditor/flags"):
        print(f"Auditor: {flag['word']} · {flag['work_id'] or '-'} · {flag['text']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the demo's morning on the current database.")
    parser.add_argument("--reset", action="store_true", help="empty the database and the uploads folder first")
    args = parser.parse_args(argv)
    settings = get_settings()
    if settings.scenario_seed != 1:
        print("The demo uses test case 1: set SCENARIO_SEED=1.")
        return 1
    init_db()
    if not args.reset and _already_seeded():
        print("The demo morning is already in the record. Run with --reset to start again.")
        return 0
    if not PHOTOS.is_file():
        print("Make the demo photos first: python -m scripts.make_demo_photos")
        return 1
    if args.reset:
        base = Path(settings.uploads_dir).resolve()
        if base.name != "uploads":
            print("UPLOADS_DIR must be a folder named uploads. Nothing was deleted.")
            return 1
        _reset(base)
        print("Emptied the database and the uploads folder.")
    # shortcut: drives the app in-process, so no server is needed
    with TestClient(app, raise_server_exceptions=False) as c:
        try:
            _morning(c)
        except StepFailed as e:
            print(e)
            return 1
    if args.reset:
        print("Restart the API now so it forgets the old runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
