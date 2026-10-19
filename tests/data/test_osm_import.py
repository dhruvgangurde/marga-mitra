import math

import pytest

from data.osm_import import load_ways

pytestmark = pytest.mark.usefixtures("need_snapshot")

KEPT = {"trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service"}


def test_enough_ways():
    assert len(load_ways()) >= 100


def test_ids_unique_and_sorted():
    ids = [w.id for w in load_ways()]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)


def test_nodes_match_coords():
    for w in load_ways():
        assert len(w.nodes) == len(w.coords) >= 2


def test_highway_tags_are_kept_classes():
    for w in load_ways():
        assert w.tags.get("highway") in KEPT


def test_coordinates_are_finite():
    for w in load_ways():
        for lon, lat in w.coords:
            assert math.isfinite(lon) and math.isfinite(lat)
