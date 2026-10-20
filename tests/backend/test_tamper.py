import json

import pytest

from backend.app import ledger
from backend.app.db import session
from scripts import tamper_demo


def _verify():
    with session() as s:
        return ledger.verify(s)


@pytest.fixture
def record(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with session() as s:
        ledger.append(s, "system", "scenario.loaded", "scenario:1", "Loaded test case 1", {})
        ledger.append(s, "ward_engineer", "plan.approved", "plan:P-0001", "Approved the plan for 2–29 Nov", {})
        ledger.append(s, "photo_check", "deposit.held", "work:T-230", "₹1,00,000 held for T-230", {})
    return tmp_path


def test_change_and_restore(record, capsys):
    assert tamper_demo.main([]) == 0
    assert "#2" in capsys.readouterr().out
    assert (_verify().ok, _verify().first_bad_seq) == (False, 2)
    backup = json.loads((record / ".cache" / "tamper_backup.json").read_text(encoding="utf-8"))
    assert backup == {"seq": 2, "summary": "Approved the plan for 2–29 Nov"}
    assert tamper_demo.main([]) == 1

    assert tamper_demo.main(["--restore"]) == 0
    assert _verify().ok
    capsys.readouterr()
    assert tamper_demo.main(["--restore"]) == 0
    assert capsys.readouterr().out.strip() == "Nothing to restore."


def test_change_a_chosen_entry(record):
    assert tamper_demo.main(["--seq", "3"]) == 0
    assert _verify().first_bad_seq == 3
    tamper_demo.main(["--restore"])
    assert _verify().ok
    assert tamper_demo.main(["--seq", "99"]) == 1
