from solver.solve import main


def test_cli_prints_a_readable_plan(capsys):
    main(["--seed", "0", "--no-risk"])
    out = capsys.readouterr().out
    assert "Test case 0" in out
    assert "Digs per road" in out
