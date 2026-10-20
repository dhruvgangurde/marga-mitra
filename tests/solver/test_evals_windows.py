import pytest

from contracts.fakes import tiny_scenario
from evals.imports import optional
from evals.run import eval_windows, load_parts, rain_spell


def test_seed_one_gets_the_demo_rain():
    w = rain_spell(tiny_scenario(1))
    assert (w.start_day, w.end_day) == (12, 13)
    assert w.label == "Heavy rain, 14–15 Nov"
    assert w.window_id == "EVAL-RAIN-1"


@pytest.mark.parametrize(("seed", "start"), [(2, 9), (3, 19), (4, 17)])
def test_other_seeds_get_a_seeded_spell(seed, start):
    w = rain_spell(tiny_scenario(seed))
    assert (w.start_day, w.end_day) == (start, start + 1)


def test_stand_in_windows_add_the_spell_on_low_roads():
    parts = load_parts(use_real=False)
    windows = eval_windows(tiny_scenario(2), parts)
    assert [w.window_id for w in windows] == ["R1", "EVAL-RAIN-2"]
    assert windows[1].segment_ids == ["S-0002"]
    assert [w.window_id for w in eval_windows(tiny_scenario(2), parts, with_rain=False)] == ["R1"]


def test_stand_ins_are_named():
    assert load_parts(use_real=False).stand_ins == ["data.scenario", "risk.windows", "agents.coordinator"]


def test_only_a_missing_module_counts_as_missing():
    assert optional("evals.not_merged_yet", "f") is None
    assert optional("json", "dumps") is not None


def test_a_missing_dependency_inside_a_merged_module_is_raised(monkeypatch):
    def broken(module):
        raise ModuleNotFoundError("No module named 'shapely'", name="shapely")

    monkeypatch.setattr("evals.imports.importlib.import_module", broken)
    with pytest.raises(ModuleNotFoundError):
        optional("data.scenario", "generate_scenario")
