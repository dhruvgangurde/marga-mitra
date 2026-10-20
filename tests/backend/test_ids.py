from backend.app.db import session
from backend.app.ids import next_id, next_work_id
from contracts.fakes import tiny_scenario
from contracts.models import Dept


def test_next_id_counts_per_prefix(db):
    with session() as s:
        ids = [next_id(s, p) for p in ("RUN", "RUN", "A", "CR", "OV")]
    assert ids == ["RUN-0001", "RUN-0002", "A-0001", "CR-0001", "OV-1"]


def test_next_work_id_starts_at_131():
    s = tiny_scenario(1)
    assert next_work_id(s, Dept.water) == "W-131"
    s.works.append(s.works[0].model_copy(update={"work_id": "W-131"}))
    assert next_work_id(s, Dept.water) == "W-132"
    assert next_work_id(s, Dept.telecom) == "T-131"
