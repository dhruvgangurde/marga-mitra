"""The demo story on the real roads of test case 1."""
import pytest

pytest.importorskip("data.scenario")

from evals.run import load_parts  # noqa: E402
from evals.story import story  # noqa: E402

GAS_PINNED = ("T3 (Requests): without a model the gas agent picks trenchless on its asked day, so the negotiation pins "
              "G-310 to day 8, inside the shared trench, instead of moving it after the trench")
NAMES = [
    "Old way digs one Munchur segment 4 times",
    "Old way has 9 clashes",
    "Water and Telecom share one trench",
    pytest.param("Gas starts after the trench", marks=pytest.mark.xfail(reason=GAS_PINNED, strict=True)),
    "Resurfacing comes last",
    "Protected roads are not cut",
    "No trench in the rain",
    "The rain works moved",
    "The procession route stays free",
]


@pytest.fixture(scope="module")
def checks() -> dict[str, bool]:
    return dict(story(load_parts())[0])


def test_every_story_check_is_named(checks):
    assert list(checks) == [n if isinstance(n, str) else n.values[0] for n in NAMES]


@pytest.mark.parametrize("name", NAMES)
def test_story_check(checks, name):
    assert checks[name], name
