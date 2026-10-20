from contracts.models import Mode
from data import check
from data.demo import DEMO_ROADS, demo_scenario


def test_main_passes(need_snapshot, capsys):
    assert check.main([]) == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert "14 passed, 0 warnings, 0 failed" in out


def test_low_lying_munchur_fails(need_snapshot):
    scenario = demo_scenario()
    first = DEMO_ROADS["Munchur Road"][0]
    segments = [s.model_copy(update={"low_lying": True}) if s.segment_id == first else s for s in scenario.segments]
    lines = check.road_lines(scenario.model_copy(update={"segments": segments}))
    assert any(status == "FAIL" and first in text for status, text in lines)


def test_p120_without_trenchless_fails(need_snapshot):
    scenario = demo_scenario()
    works = [
        w.model_copy(update={"modes": [m for m in w.modes if m.mode == Mode.open_cut]}) if w.work_id == "P-120" else w
        for w in scenario.works
    ]
    lines = check.road_lines(scenario.model_copy(update={"works": works}))
    assert any(status == "FAIL" and "P-120" in text and "trenchless" in text for status, text in lines)


def test_story_passes(need_snapshot):
    lines = check.story_lines(demo_scenario())
    assert not [line for line in lines if line[0] == "FAIL"]
    assert "10\u201315 Nov" in lines[0][1]


def test_late_telecom_breaks_the_trench(need_snapshot):
    scenario = demo_scenario()
    works = [w.model_copy(update={"earliest_start": 11}) if w.work_id == "T-221" else w for w in scenario.works]
    lines = check.story_lines(scenario.model_copy(update={"works": works}))
    assert lines[0][0] == "FAIL" and "no common dates" in lines[0][1]


def test_tight_w118_breaks_the_procession(need_snapshot):
    scenario = demo_scenario()
    works = [w.model_copy(update={"latest_end": 13}) if w.work_id == "W-118" else w for w in scenario.works]
    lines = check.story_lines(scenario.model_copy(update={"works": works}))
    assert any(status == "FAIL" and "W-118" in text for status, text in lines)
