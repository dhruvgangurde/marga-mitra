from datetime import datetime
from itertools import combinations

from backend.app.verify.decide import distance_m
from backend.app.verify.exif import INDIA, read_photo_facts
from backend.app.verify.phash import distance, fingerprint
from contracts.fakes import tiny_scenario
from scripts.make_demo_photos import make_photo, reuse_copy, site_point, with_facts


def _print(img) -> str:
    return fingerprint(with_facts(img, None, None, None))


def test_site_point():
    assert site_point(tiny_scenario(1), "W-001", 12) == (13.010108, 74.793)


def test_site_point_lies_on_a_bent_road():
    s = tiny_scenario(1)
    bent = [(74.792, 13.01), (74.795, 13.01), (74.795, 13.011)]  # an L: the average of its ends is off the road
    s.segments[1] = s.segments[1].model_copy(update={"coords": bent})
    lat, lon = site_point(s, "W-001", 0)
    assert distance_m((lon, lat), [bent]) < 0.5


def test_with_facts_round_trips():
    taken = datetime(2026, 11, 10, 8, 12, tzinfo=INDIA)
    data = with_facts(make_photo("open", 1041), 13.010108, 74.793, taken)
    assert read_photo_facts(data) == (13.010108, 74.793, taken)
    assert read_photo_facts(with_facts(make_photo("open", 1041), None, None, None)) == (None, None, None)


def test_make_photo_is_deterministic():
    assert make_photo("patched", 1041).tobytes() == make_photo("patched", 1041).tobytes()


def test_reused_photo_is_close():
    assert distance(_print(reuse_copy(make_photo("open", 2211))), _print(make_photo("open", 2211))) <= 8


def test_different_sites_are_far_apart():
    prints = [_print(make_photo("open", seed)) for seed in (1041, 2211, 2301, 1251)]
    assert all(distance(a, b) >= 16 for a, b in combinations(prints, 2))
