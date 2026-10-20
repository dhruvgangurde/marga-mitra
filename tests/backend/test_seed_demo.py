import importlib.util

import pytest

from backend.app import ledger, store
from backend.app.config import get_settings
from backend.app.db import session
from scripts import seed_demo


def _entries() -> list:
    with session() as s:
        return ledger.latest(s, 500)


def _seeded() -> None:
    with session() as s:
        ledger.append(s, "resident", "emergency.reported", "work:W-131", "Reported a burst water pipe on Idya lane", {})


@pytest.fixture
def settings_env(monkeypatch):
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_runs_once(db, capsys):
    _seeded()
    assert seed_demo.main([]) == 0
    assert "already in the record" in capsys.readouterr().out
    assert len(_entries()) == 1


def test_needs_test_case_1(db, settings_env):
    settings_env.setenv("SCENARIO_SEED", "2")
    get_settings.cache_clear()
    assert seed_demo.main([]) == 1


def test_reset_only_empties_a_folder_named_uploads(db, settings_env, tmp_path, capsys):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "keep.jpg").write_bytes(b"x")
    settings_env.setenv("UPLOADS_DIR", str(photos))
    get_settings.cache_clear()
    _seeded()
    assert seed_demo.main(["--reset"]) == 1
    assert "UPLOADS_DIR must be a folder named uploads. Nothing was deleted." in capsys.readouterr().out
    assert (photos / "keep.jpg").exists()
    assert len(_entries()) == 1


@pytest.mark.skipif(not all(importlib.util.find_spec(m) for m in ("data.scenario", "solver.solve", "agents.workflow"))
                    or not seed_demo.PHOTOS.is_file(), reason="needs the other tracks and the demo photos")
def test_replays_the_morning(db, uploads_dir):
    from langgraph.checkpoint.memory import InMemorySaver

    from agents import workflow

    workflow.set_checkpointer(InMemorySaver())
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "old.jpg").write_bytes(b"x")
    assert seed_demo.main(["--reset"]) == 0
    assert uploads_dir.is_dir() and not (uploads_dir / "old.jpg").exists()

    entries = _entries()
    assert ("emergency.reported", "work:W-131") in {(e.action, e.entity) for e in entries}
    assert ("plan.rejected", "ward_engineer") in {(e.action, e.actor) for e in entries}
    assert ("deposit.held", "work:T-230") in {(e.action, e.entity) for e in entries}
    with session() as s:
        assert ledger.verify(s).ok
        flags = {(f.severity, f.word, f.work_id) for f in store.list_flags(s, 1)}
    assert flags == {("fail", "Photo reused", "T-230"), ("ok", "Reviewed", "W-131")}

    assert seed_demo.main([]) == 0
    assert len(_entries()) == len(entries)
