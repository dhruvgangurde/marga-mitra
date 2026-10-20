"""Where planning runs that wait for approval are kept, so a paused run survives an API restart."""
import contextlib
import logging
from typing import Any

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


async def open_run_store(stack: contextlib.AsyncExitStack, wiring: Any) -> str:
    """Give the real workflow a Postgres checkpointer; returns "none", "postgres" or "memory"."""
    if getattr(wiring.start_run, "__module__", "") != "agents.workflow":
        return "none"  # a stand-in keeps no paused runs
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from agents import workflow

    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    # Windows: psycopg's async mode refuses the Proactor event loop; uvicorn uses the selector loop only with --reload, so plain uvicorn on Windows falls back to memory.
    try:
        # shortcut: one connection shared by all runs (the saver locks it); switch to an AsyncConnectionPool if many runs pause at once.
        saver = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(url))
        await saver.setup()
        workflow.set_checkpointer(saver)
        logger.info("Paused planning runs are kept in Postgres.")
        return "postgres"
    except Exception as exc:
        logger.warning("Paused planning runs are kept in memory only (%s): an API restart forgets them.", type(exc).__name__)
        return "memory"
