from datetime import UTC, datetime

import pytest

from backend.app import store
from backend.app.deps import in_session
from contracts.fakes import tiny_scenario
from contracts.models import Assignment, Plan


@pytest.fixture
def solved(client, monkeypatch):
    """Keeps the constraints every solve gets."""
    deps = client.app.state.wiring.deps
    seen = []

    def spy(scenario, constraints, variant):
        seen.append(constraints)
        return solve(scenario, constraints, variant)

    solve = deps.solve
    monkeypatch.setattr(deps, "solve", spy)
    return seen


def _ask(client, work_id: str, delay_days: int):
    return client.post("/plan/whatif", json={"work_id": work_id, "delay_days": delay_days})


def test_whatif_on_the_old_way(client, solved):
    entries = client.get("/ledger/verify").json()["entries"]
    r = _ask(client, "W-001", 2).json()
    assert (r["plan"]["plan_id"], r["plan"]["variant"], r["plan"]["base_plan_id"]) == ("P-WHATIF", "whatif", "P-OLD-1")
    assert (r["diff"], r["metrics"]["plan_id"]) == ([], "P-WHATIF")
    [c] = solved
    assert (c.min_start, c.pinned_start, c.shared_groups) == ({"W-001": 10, "T-001": 10, "R-001": 9}, {"G-001": 9}, [])
    assert "P-WHATIF" not in {p["plan_id"] for p in client.get("/plans").json()}
    assert client.get("/plan/P-WHATIF").status_code == 404
    assert client.get("/ledger/verify").json()["entries"] == entries


def test_whatif_moves_the_shared_trench(client, solved):
    def a(wid: str, start: int, end: int, group: str | None = None) -> Assignment:
        return Assignment(work_id=wid, start_day=start, end_day=end, mode="open_cut", shared_group=group)

    in_session(store.save_plan, Plan(
        plan_id="P-0001", seed=1, variant="orchestrated", status="approved", created_at=datetime.now(UTC),
        assignments=[a("W-001", 8, 12, "G1"), a("T-001", 8, 12, "G1"), a("G-001", 9, 12), a("R-001", 13, 15)]))
    assert _ask(client, "T-001", 2).json()["plan"]["base_plan_id"] == "P-0001"
    [c] = solved
    assert (c.min_start, c.pinned_start, c.shared_groups) == ({"T-001": 10, "W-001": 8, "R-001": 13}, {"G-001": 9}, ["G1"])


def test_whatif_refuses(client):
    assert _ask(client, "W-999", 2).status_code == 404
    assert _ask(client, "W-001", 0).status_code == 422
    assert _ask(client, "W-001", 15).status_code == 422
    work = tiny_scenario(1).works[0]
    client.post("/works", json=work.model_copy(update={"work_id": "W-131", "is_emergency": True}).model_dump(mode="json"))
    r = _ask(client, "W-131", 2)
    assert (r.status_code, r.json()["detail"]) == (422, "An emergency dig cannot be moved.")
    client.post("/works", json=work.model_copy(update={"work_id": "W-132"}).model_dump(mode="json"))
    r = _ask(client, "W-132", 2)
    assert (r.status_code, r.json()["detail"]) == (422, "W-132 is not in the current plan.")
