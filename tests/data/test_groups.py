import random

from contracts import costs, fakes
from contracts.models import Dept, RoadClass, Segment
from data.groups import find_parallel_groups


def _segments(n: int) -> list[Segment]:
    return [
        Segment(
            segment_id=f"S-{i:04d}",
            osm_way_id=i,
            road_class=RoadClass.residential,
            length_m=100.0,
            lanes=1,
            traffic_weight=1.0,
            coords=[(74.79, 13.0), (74.791, 13.0)],
        )
        for i in range(1, n + 1)
    ]


def _ids(first: int, last: int) -> list[str]:
    return [f"S-{i:04d}" for i in range(first, last + 1)]


def test_tiny_scenario_has_one_group():
    scenario = fakes.tiny_scenario()
    groups = find_parallel_groups(scenario.works, scenario.segments)
    assert len(groups) == 1
    assert groups[0].group_id == "G1"
    assert groups[0].work_ids == ["T-001", "W-001"]
    pair = sorted((w for w in scenario.works if w.work_id in ("W-001", "T-001")), key=lambda w: w.work_id)
    assert groups[0].saving_inr == costs.shared_trench_saving_inr(pair)


def test_roads_and_done_works_are_never_grouped():
    scenario = fakes.tiny_scenario()
    roads_like = [w.model_copy(update={"dept": Dept.roads}) if w.work_id == "T-001" else w for w in scenario.works]
    assert find_parallel_groups(roads_like, scenario.segments) == []
    done = [w.model_copy(update={"done": True}) if w.work_id == "T-001" else w for w in scenario.works]
    assert find_parallel_groups(done, scenario.segments) == []
    emergency = [w.model_copy(update={"is_emergency": True}) if w.work_id == "T-001" else w for w in scenario.works]
    assert find_parallel_groups(emergency, scenario.segments) == []


def _pair(first_b: int, last_b: int):
    base = fakes.tiny_scenario().works
    a = base[0].model_copy(update={"work_id": "W-900", "segment_ids": _ids(1, 10), "length_m": 1000.0})
    b = base[1].model_copy(update={"work_id": "T-900", "segment_ids": _ids(first_b, last_b), "length_m": 1000.0})
    return [a, b], _segments(20)


def test_half_overlap_is_not_enough():
    works, segments = _pair(6, 15)  # shares 5 of 10 segments = 50%
    assert find_parallel_groups(works, segments) == []


def test_seventy_percent_overlap_is_a_group():
    works, segments = _pair(4, 13)  # shares 7 of 10 segments = 70%
    groups = find_parallel_groups(works, segments)
    assert len(groups) == 1
    assert groups[0].work_ids == ["T-900", "W-900"]
    assert groups[0].segment_ids == _ids(4, 10)


def test_shuffled_input_gives_the_same_groups():
    scenario = fakes.tiny_scenario()
    expected = find_parallel_groups(scenario.works, scenario.segments)
    works = list(scenario.works)
    segments = list(scenario.segments)
    for seed in range(5):
        random.Random(seed).shuffle(works)
        random.Random(seed).shuffle(segments)
        assert find_parallel_groups(works, segments) == expected
