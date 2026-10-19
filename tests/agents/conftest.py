import pytest
from langgraph.checkpoint.memory import InMemorySaver

from agents import workflow
from agents.llm import get_llm


@pytest.fixture(autouse=True)
def _no_model_unless_a_test_asks(monkeypatch):
    # .env may hold a real key; tests must never reach the network
    monkeypatch.setenv("LLM_PROVIDER", "none")
    get_llm.cache_clear()
    yield
    get_llm.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_runs():
    # run ids repeat across tests, so each test gets its own checkpoints
    workflow.set_checkpointer(InMemorySaver())
    workflow._deps.clear()
    yield
    workflow.set_checkpointer(InMemorySaver())
