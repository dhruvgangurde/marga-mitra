import subprocess
import sys
from pathlib import Path

from contracts.models import Mode
from data import check
from data.demo import DEMO_ROADS, demo_scenario
from data.scenario import generate_scenario


def test_main_passes(need_snapshot, capsys):
    assert check.main([]) == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert ", 0 failed" in out


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


def test_seed_lines_summary():
    lines = check.seed_lines(range(2, 5))
    assert not [line for line in lines if line[0] == "FAIL"]
    assert lines[-1][1].startswith("Test cases 2\u20134")


def test_seed_lines_table():
    lines = check.seed_lines([2], table=True)
    assert any(text.startswith("test case 2:") for _, text in lines)


def test_export_is_up_to_date(need_snapshot, tmp_path):
    out = tmp_path / "scenario.json"
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, "-m", "data.demo", "--out", str(out)], cwd=root, check=True, capture_output=True)
    assert check.export_line(out) == ("PASS", "the web export is up to date")


def test_export_from_another_seed_is_out_of_date(need_snapshot, tmp_path):
    out = tmp_path / "scenario.json"
    out.write_text(generate_scenario(2).model_dump_json(), encoding="utf-8")
    status, text = check.export_line(out)
    assert status == "FAIL" and text.startswith("the web export is out of date: run python -m data.demo --out")


def test_missing_export(tmp_path):
    out = tmp_path / "none.json"
    assert check.export_line(out) == ("FAIL", f"no web export at {out}")
