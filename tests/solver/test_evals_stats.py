import pytest

from contracts.models import Stat
from evals.run import parse_seeds
from evals.stats import stat


def test_stat():
    assert stat([3.0]) == Stat(median=3.0, low=3.0, high=3.0)
    assert stat([1, 2]) == Stat(median=1.5, low=1.1, high=1.9)
    assert stat([1, 2, 3, 4, 5]) == Stat(median=3.0, low=1.4, high=4.6)
    assert stat([10, 0, 5, 20]) == Stat(median=7.5, low=1.5, high=17.0)
    assert stat([4, 4, 4, 4]) == Stat(median=4.0, low=4.0, high=4.0)


def test_stat_needs_values():
    with pytest.raises(ValueError, match="no values"):
        stat([])


def test_parse_seeds():
    assert parse_seeds("1-3,7") == [1, 2, 3, 7]
    assert parse_seeds("5") == [5]
    assert parse_seeds("2,1,2") == [1, 2]
    assert len(parse_seeds("1-50")) == 50


@pytest.mark.parametrize("text", ["", "a", "3-1", "0"])
def test_parse_seeds_rejects(text):
    with pytest.raises(ValueError):
        parse_seeds(text)
