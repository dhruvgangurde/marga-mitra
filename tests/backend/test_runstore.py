import asyncio
import contextlib
import logging
from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy import text

from backend.app.db import engine
from backend.app.runstore import open_run_store
from contracts.fakes import fake_start_run


async def _open(wiring: SimpleNamespace) -> str:
    async with contextlib.AsyncExitStack() as stack:
        return await open_run_store(stack, wiring)


async def test_stand_in_keeps_no_runs():
    assert await _open(SimpleNamespace(start_run=fake_start_run)) == "none"


async def test_falls_back_to_memory(monkeypatch, caplog):
    workflow = pytest.importorskip("agents.workflow")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    def refuse(url: str):
        raise psycopg.InterfaceError("no")

    calls: list[object] = []
    monkeypatch.setattr(AsyncPostgresSaver, "from_conn_string", refuse)
    monkeypatch.setattr(workflow, "set_checkpointer", calls.append)
    with caplog.at_level(logging.WARNING):
        assert await _open(SimpleNamespace(start_run=workflow.start_run)) == "memory"
    assert "Paused planning runs are kept in memory only (InterfaceError)" in caplog.text
    assert [type(c).__name__ for c in calls] == ["InMemorySaver"]  # only the reset on exit, never a Postgres saver


def test_keeps_runs_in_postgres(db):
    workflow = pytest.importorskip("agents.workflow")
    from langgraph.checkpoint.memory import InMemorySaver

    try:
        # psycopg's async mode needs the selector loop, also on Windows
        found = asyncio.run(_open(SimpleNamespace(start_run=workflow.start_run)), loop_factory=asyncio.SelectorEventLoop)
        assert found == "postgres"
        assert type(workflow._saver).__name__ == "InMemorySaver"  # the closed connection's saver is gone on exit
        with engine().connect() as c:
            assert c.execute(text("SELECT to_regclass('public.checkpoints')")).scalar() is not None
    finally:
        workflow.set_checkpointer(InMemorySaver())
