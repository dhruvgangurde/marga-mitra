import json

import pytest

from contracts.models import RoadClass, Segment
from data import elevation
from data.segments import build_segments, load_segments

FETCH_HINT = "Run: python -m data.elevation --fetch"


def _segment(n: int) -> Segment:
    return Segment(
        segment_id=f"S-{n:04d}",
        osm_way_id=n,
        road_class=RoadClass.residential,
        length_m=100.0,
        lanes=1,
        traffic_weight=1.0,
        coords=[(74.79, 13.0), (74.791, 13.0)],
    )


def test_apply_elevation_marks_the_lowest_one(tmp_path, monkeypatch):
    path = tmp_path / "elevations.json"
    path.write_text(
        json.dumps({"elevations": {"S-0001": 30.0, "S-0002": 12.5, "S-0003": 20.0, "S-0004": 45.0, "S-0005": 8.0}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(elevation, "ELEVATIONS", path)
    segments = [_segment(i) for i in range(1, 6)]
    result = elevation.apply_elevation(segments)
    assert [s.segment_id for s in result if s.low_lying] == ["S-0005"]
    assert [s.elevation_m for s in result] == [30.0, 12.5, 20.0, 45.0, 8.0]
    assert all(s.elevation_m is None and not s.low_lying for s in segments)


def test_apply_elevation_without_file_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(elevation, "ELEVATIONS", tmp_path / "missing.json")
    segments = [_segment(1), _segment(2)]
    result = elevation.apply_elevation(segments)
    assert result == segments
    assert result[0] is not segments[0]


@pytest.fixture
def need_elevations(need_snapshot):
    if not elevation.ELEVATIONS.exists():
        pytest.skip(FETCH_HINT)


def test_every_segment_has_an_elevation(need_elevations):
    known = json.loads(elevation.ELEVATIONS.read_text(encoding="utf-8"))["elevations"]
    assert all(s.segment_id in known for s in build_segments())


def test_low_lying_share(need_elevations):
    segments = load_segments()
    low = [s for s in segments if s.low_lying]
    assert len(low) == round(0.2 * len(segments))
    top_low = max(s.elevation_m for s in low)
    assert all(s.elevation_m >= top_low for s in segments if not s.low_lying)
