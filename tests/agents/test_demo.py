from agents.department import demo
from agents.llm import get_llm


async def test_demo_runs_one_round_without_a_model(monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    get_llm.cache_clear()
    await demo()
    get_llm.cache_clear()
    lines = capsys.readouterr().out.splitlines()
    messages = [ln for ln in lines if ln.split(" ", 1)[0] in ("ACCEPT", "COUNTER", "ESCALATE")]
    assert len(messages) == 10
    assert sum(ln.startswith("ACCEPT") for ln in messages) == 8
    assert sum(ln.startswith("COUNTER") for ln in messages) == 2
    assert all(ln.endswith("(fallback)") for ln in messages)
    assert sum(ln.startswith("    ") for ln in lines) == 5
