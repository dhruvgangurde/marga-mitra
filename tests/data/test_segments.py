import pytest

from contracts.models import RoadClass
from data.osm_import import load_ways
from data.segments import (
    LANES_BY_CLASS,
    MAP_BOUNDS,
    TRAFFIC_WEIGHT,
    haversine_m,
    lanes_for,
    line_length_m,
    load_segments,
)

snapshot = pytest.mark.usefixtures("need_snapshot")


def test_haversine_one_degree_of_latitude():
    assert haversine_m((74.8, 13.0), (74.8, 14.0)) == pytest.approx(111_195, abs=50)


def test_lanes_tag_rules():
    assert lanes_for({"lanes": "2;3"}, RoadClass.service) == 2
    assert lanes_for({"lanes": "9"}, RoadClass.service) == 6
    assert lanes_for({"lanes": "0"}, RoadClass.service) == 1
    assert lanes_for({"lanes": "many"}, RoadClass.trunk) == 4
    assert lanes_for({}, RoadClass.residential) == 1


@snapshot
def test_two_calls_are_equal():
    assert load_segments() == load_segments()


@snapshot
def test_ids_run_without_gaps():
    ids = [s.segment_id for s in load_segments()]
    assert ids == [f"S-{i:04d}" for i in range(1, len(ids) + 1)]


@snapshot
def test_lengths():
    for s in load_segments():
        assert 0 < s.length_m <= 300.5
        assert s.length_m == pytest.approx(line_length_m(s.coords), abs=0.5)


@snapshot
def test_lanes_and_weight_follow_tables():
    tags = {w.id: w.tags for w in load_ways()}
    for s in load_segments():
        assert s.traffic_weight == TRAFFIC_WEIGHT[s.road_class]
        if not any(ch.isdigit() for ch in tags[s.osm_way_id].get("lanes", "")):
            assert s.lanes == LANES_BY_CLASS[s.road_class]


@snapshot
def test_neighbors_are_symmetric():
    by_id = {s.segment_id: s for s in load_segments()}
    for s in by_id.values():
        assert s.segment_id not in s.neighbors
        assert s.neighbors == sorted(s.neighbors)
        for other in s.neighbors:
            assert s.segment_id in by_id[other].neighbors


@snapshot
def test_midpoints_inside_bounds():
    min_lon, min_lat, max_lon, max_lat = MAP_BOUNDS
    for s in load_segments():
        lon = (s.coords[0][0] + s.coords[-1][0]) / 2
        lat = (s.coords[0][1] + s.coords[-1][1]) / 2
        assert min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


@snapshot
def test_editing_a_result_changes_nothing_next_time():
    first = load_segments()
    first[0].lanes = 99
    first[0].neighbors.append("S-9999")
    first[0].coords.append((0.0, 0.0))
    assert load_segments()[0].lanes != 99
    assert load_segments() == load_segments()
    assert "S-9999" not in load_segments()[0].neighbors