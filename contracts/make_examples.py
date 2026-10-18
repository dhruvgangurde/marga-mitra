"""Writes contracts/examples/*.json from the fakes, so the web app can run on mock data. Run: python -m contracts.make_examples"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from contracts.fakes import MemoryStore, fake_deps, fake_start_run, now
from contracts.models import (
    LedgerVerify,
    Verification,
    VerificationCheck,
    WorkStatus,
    WorkView,
)

OUT = Path(__file__).resolve().parent / "examples"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    store = MemoryStore()
    deps = fake_deps(store)
    scenario = deps.generate_scenario(1)
    run = asyncio.run(fake_start_run(deps, "RUN-0001", 1))
    plan = store.plans[run.plan_id]
    approval = store.approvals[run.approval_id]
    views = [WorkView(work=w, assignment=next(a for a in plan.assignments if a.work_id == w.work_id), status=WorkStatus.planned)
             for w in scenario.works]
    verification = Verification(verification_id="V-0001", work_id="W-001", result="verified", deposit_inr=scenario.works[0].deposit_inr,
                                deposit_released=True, decided_at=now(), checks=[
                                    VerificationCheck(name="place", status="ok", detail="Both photos within 12 m of the site"),
                                    VerificationCheck(name="reuse", status="ok", detail="Not seen in any other work")])
    files = {
        "scenario.json": scenario.model_dump(mode="json"),
        "plan.json": plan.model_dump(mode="json"),
        "metrics.json": run.metrics.model_dump(mode="json") if run.metrics else None,
        "run_result.json": run.model_dump(mode="json"),
        "approval.json": approval.model_dump(mode="json"),
        "work_views.json": [v.model_dump(mode="json") for v in views],
        "ledger.json": [e.model_dump(mode="json") for e in store.ledger],
        "ledger_verify.json": LedgerVerify(ok=True, entries=len(store.ledger)).model_dump(mode="json"),
        "ws_events.json": [e.model_dump(mode="json") for e in store.events],
        "verification.json": verification.model_dump(mode="json"),
    }
    for name, data in files.items():
        (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} files to {OUT}")


if __name__ == "__main__":
    main()
