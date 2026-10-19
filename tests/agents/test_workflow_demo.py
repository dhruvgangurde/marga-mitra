from agents.workflow import demo


async def test_the_demo_shows_the_whole_run(capsys):
    await demo()
    out = capsys.readouterr().out
    for expected in ("M001", "DECISION", "Waiting for approval A-0001", "Approved: plan P-DEMO",
                     "#3 ward_engineer plan.approved"):
        assert expected in out
