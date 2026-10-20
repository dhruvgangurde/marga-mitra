from datetime import timedelta

import pytest
from sqlalchemy import func, select

from backend.app import store
from backend.app.db import session
from backend.app.tables import SegmentRow
from contracts.fakes import fake_naive_plan, now, tiny_scenario
from contracts.models import NegotiationMessage, Plan, PlanStatus


def _plan(plan_id: str, status: PlanStatus) -> Plan:
    return fake_naive_plan(tiny_scenario(1)).model_copy(update={"plan_id": plan_id, "status": status})


def _loaded() -> None:
    with session() as s:
        store.put_scenario(s, tiny_scenario(1))


def test_scenario_round_trip(db):
    _loaded()
    with session() as s:
        assert store.get_scenario(s, 1) == tiny_scenario(1)
        assert store.get_scenario(s, 2) is None
        assert s.scalar(select(func.count()).select_from(SegmentRow)) == 3


def test_add_work_rules(db):
    _loaded()
    gas = tiny_scenario(1).works[2]
    with session() as s:
        store.add_work(s, 1, gas.model_copy(update={"work_id": "G-002"}))
    with session() as s:
        assert store.get_scenario(s, 1).works[-1].work_id == "G-002"
        with pytest.raises(ValueError, match="exists"):
            store.add_work(s, 1, gas)
        with pytest.raises(ValueError, match="unknown segment"):
            store.add_work(s, 1, gas.model_copy(update={"work_id": "G-003", "segment_ids": ["S-9999"]}))


def test_bbox_picks_one_segment(db):
    _loaded()
    with session() as s:
        everything = store.segments_geojson(s, None)
        picked = store.segments_geojson(s, (74.789, 13.0, 74.7915, 13.02))
    assert len(everything["features"]) == 3
    assert [f["properties"]["segment_id"] for f in picked["features"]] == ["S-0001"]
    assert picked["features"][0]["geometry"] == {"type": "LineString", "coordinates": [[74.79, 13.01], [74.792, 13.01]]}


def test_approved_plan_supersedes_the_older_one(db):
    with session() as s:
        store.save_plan(s, _plan("P-0001", PlanStatus.approved))
        store.save_plan(s, _plan("P-0002", PlanStatus.approved))
    with session() as s:
        assert store.get_plan(s, "P-0001").status == PlanStatus.superseded
        assert [(p.plan_id, p.status) for p in store.list_plans(s, 1)] == [
            ("P-0002", PlanStatus.approved), ("P-0001", PlanStatus.superseded)]


def test_active_plan_rule(db):
    with session() as s:
        assert store.active_plan(s, 1) is None
        store.save_plan(s, _plan("P-OLD-1", PlanStatus.draft))
        assert store.active_plan(s, 1).plan_id == "P-OLD-1"
        store.save_plan(s, _plan("P-0001", PlanStatus.waiting_approval))
        assert store.active_plan(s, 1).plan_id == "P-0001"
        store.save_plan(s, _plan("P-0002", PlanStatus.approved))
        assert store.active_plan(s, 1).plan_id == "P-0002"


def test_messages_come_back_oldest_first(db):
    def msg(i: int, minutes: int) -> NegotiationMessage:
        return NegotiationMessage(msg_id=f"M{i}", run_id="RUN-0001", round=1, sender="coordinator", recipients=["water"],
                                  type="NOTICE", work_ids=["W-001"], body=f"Message {i}", ts=now() + timedelta(minutes=minutes))

    with session() as s:
        for m in (msg(3, 2), msg(1, 0), msg(2, 1), msg(1, 0)):
            store.save_message(s, m)
    with session() as s:
        assert [m.msg_id for m in store.list_messages(s, "RUN-0001")] == ["M1", "M2", "M3"]
        assert store.list_messages(s, "RUN-9999") == []
