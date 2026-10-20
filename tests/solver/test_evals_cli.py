import csv

import pytest

from contracts.fakes import now
from contracts.models import EvalSummary, Stat
from evals import fake_repairs, run

ROW_FIELDS = ("digs_per_road", "lane_closure_hours", "trench_hours_in_rain", "clashes", "days_late", "cost_inr")


@pytest.fixture
def stand_ins(monkeypatch):
    """The test stays the same when other tracks merge."""
    parts = run.load_parts(use_real=False)
    monkeypatch.setattr(run, "load_parts", lambda: parts)
    monkeypatch.setattr(fake_repairs, "load_decide", lambda: None)


def main(tmp_path, name: str = "s.json") -> tuple:
    out, rows = tmp_path / name, tmp_path / "r.csv"
    run.main(["--seeds", "1-3", "--out", str(out), "--csv", str(rows), "--fixed-time"])
    return out, rows


def test_the_summary_file(stand_ins, tmp_path):
    out, _ = main(tmp_path)
    s = EvalSummary.model_validate_json(out.read_text(encoding="utf-8"))
    assert s.seeds == [1, 2, 3]
    assert [r.variant for r in s.rows] == list(run.VARIANTS)
    for r in s.rows:
        for f in ROW_FIELDS:
            st = getattr(r, f)
            assert st.low <= st.median <= st.high, (r.variant, f)
    rows = {r.variant: r for r in s.rows}
    assert all(getattr(rows["full"], f) == getattr(rows["risk"], f) for f in ROW_FIELDS)
    assert rows["naive"].clashes == Stat(median=4.0, low=4.0, high=4.0)
    assert s.generated_at == now()
    assert s.fake_repairs_caught == s.fake_repairs_total == 0


def test_the_runs_file_and_repeatability(stand_ins, tmp_path):
    first, rows = main(tmp_path, "a.json")
    with rows.open(encoding="utf-8", newline="") as f:
        table = list(csv.reader(f))
    assert table[0] == list(run.CSV_FIELDS)
    assert len(table) == 1 + 15
    second, _ = main(tmp_path, "b.json")
    assert first.read_bytes() == second.read_bytes()


def test_the_printed_words(stand_ins, tmp_path, capsys):
    main(tmp_path)
    printed = capsys.readouterr().out
    assert "Old way (first come, first dug)" in printed
    assert "+ photo checks (all of MargaMitra)" in printed
    assert "Stand-ins: data.scenario, risk.windows, agents.coordinator" in printed
    assert "Fake repairs caught: 0 of 0 (genuine repairs passed: 0 of 0) The photo checks are not merged yet." in printed
