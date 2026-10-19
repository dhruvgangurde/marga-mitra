import asyncio

import pytest

from agents import workflow
from agents.workflow import resume_run, start_run
from contracts.fakes import MemoryStore, fake_deps


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def deps(store):
    return fake_deps(store)


async def test_a_run_stops_at_the_approval(deps, store):
    result = await start_run(deps, "RUN-0001", 1)
    assert (result.status, result.plan_id, result.approval_id) == ("waiting_approval", "P-0001", "A-0001")
    assert result.metrics is not None
    assert result.note == ""
    plan = store.plans["P-0001"]
    assert plan.status.value == "waiting_approval"
    assert plan.base_plan_id == "P-NAIVE"
    assert [e.action for e in store.ledger] == ["plan.decided", "rules.checked"]
    assert [e.type for e in store.events] == ["negotiation.message", "negotiation.message", "approval.requested"]
    decision = store.events[1].data
    assert decision["msg_id"] == "M002"
    assert decision["sender"] == "solver"
    assert decision["type"] == "DECISION"
    assert decision["recipients"] == ["Everyone"]
    assert decision["body"] == "The new plan: digs per road 1.0 → 1.0, lane-closure hours 0 → 0, clashes 0 → 0."
    assert store.ledger[0].summary == "Scheduler made a new plan: 0 works change"
    assert store.ledger[1].summary == "Rules check passed"
    assert workflow._deps == {}


async def test_a_failed_run_says_so_and_asks_nobody(deps, store):
    def boom(*args, **kwargs):
        raise RuntimeError("scheduler down")

    deps.solve = boom
    result = await start_run(deps, "RUN-0001", 1)
    assert result.status == "failed"
    assert result.note == "The plan could not be made."
    assert store.approvals == {}
    assert workflow._deps == {}


def test_decision_body_adds_rain_only_when_there_was_some():
    from contracts.models import Metrics

    def metrics(rain):
        return Metrics(plan_id="P", excavations=1, digs_per_road=2.66, lane_closure_hours=450.0,
                       trench_hours_in_rain=rain, clashes=4, days_late=0.0, cost_inr=0, dust_score=0.0)

    assert "rain" not in workflow.decision_body(metrics(0.0), metrics(0.0))
    assert workflow.decision_body(metrics(48.0), metrics(0.0)).endswith(" Trench-hours in rain: 48 → 0.")


async def test_approving_finishes_the_run(deps, store):
    await start_run(deps, "RUN-0001", 1)
    result = await resume_run(deps, "RUN-0001", "approve", "ward_engineer")
    assert (result.status, result.plan_id, result.approval_id) == ("approved", "P-0001", "A-0001")
    assert store.plans["P-0001"].status.value == "approved"
    assert [e.action for e in store.ledger] == ["plan.decided", "rules.checked", "plan.approved"]
    assert store.ledger[-1].actor == "ward_engineer"
    assert store.ledger[-1].summary == "Approved the plan for 2–29 Nov"
    assert workflow._deps == {}


async def test_rejecting_keeps_the_reason(deps, store):
    await start_run(deps, "RUN-0001", 1)
    result = await resume_run(deps, "RUN-0001", "reject", "ward_engineer", "The gas crew is not free that week")
    assert result.status == "rejected"
    assert store.plans["P-0001"].status.value == "rejected"
    last = store.ledger[-1]
    assert last.action == "plan.rejected"
    assert last.summary == "Rejected the plan for 2–29 Nov: The gas crew is not free that week"
    assert last.payload["reason"] == "The gas crew is not free that week"


async def test_rejecting_without_a_reason_says_no_reason(deps, store):
    await start_run(deps, "RUN-0001", 1)
    await resume_run(deps, "RUN-0001", "reject", "ward_engineer")
    assert store.ledger[-1].summary == "Rejected the plan for 2–29 Nov"


async def test_bad_resumes_raise(deps):
    with pytest.raises(ValueError, match="not waiting"):
        await resume_run(deps, "RUN-9999", "approve", "ward_engineer")
    await start_run(deps, "RUN-0001", 1)
    with pytest.raises(ValueError, match="Unknown decision"):
        await resume_run(deps, "RUN-0001", "later", "ward_engineer")
    await resume_run(deps, "RUN-0001", "approve", "ward_engineer")
    with pytest.raises(ValueError, match="not waiting"):
        await resume_run(deps, "RUN-0001", "approve", "ward_engineer")


async def test_two_runs_at_once_stay_apart():
    s1, s2 = MemoryStore(), MemoryStore()
    d1, d2 = fake_deps(s1), fake_deps(s2)
    first, second = await asyncio.gather(start_run(d1, "RUN-0001", 1), start_run(d2, "RUN-0002", 1))
    assert (first.plan_id, second.plan_id) == ("P-0001", "P-0002")
    await resume_run(d2, "RUN-0002", "approve", "ward_engineer")
    await resume_run(d1, "RUN-0001", "reject", "ward_engineer", "Not now")
    assert list(s1.plans) == ["P-0001"]
    assert s1.plans["P-0001"].status.value == "rejected"
    assert list(s2.plans) == ["P-0002"]
    assert s2.plans["P-0002"].status.value == "approved"
