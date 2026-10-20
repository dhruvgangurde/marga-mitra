import os

# before any backend import: get_settings() is cached on first use
os.environ["DATABASE_URL"] = "postgresql+psycopg://margamitra:margamitra@localhost:5432/margamitra_test"
os.environ["LLM_PROVIDER"] = "none"
os.environ["WEATHER_MODE"] = "fixture"
os.environ["SCENARIO_SEED"] = "1"
os.environ["TODAY_DAY"] = "8"

from functools import cache  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.app.db import engine, init_db  # noqa: E402
from backend.app.tables import Base  # noqa: E402


@cache
def _ensure_test_db() -> bool:
    try:
        with psycopg.connect("postgresql://margamitra:margamitra@localhost:5432/postgres",
                             autocommit=True, connect_timeout=3) as c:
            if not c.execute("SELECT 1 FROM pg_database WHERE datname = 'margamitra_test'").fetchone():
                c.execute("CREATE DATABASE margamitra_test")
        return True
    except psycopg.OperationalError:
        return False


@pytest.fixture
def db():
    if not _ensure_test_db():
        pytest.skip("start the database: docker compose up -d db")
    init_db()
    with engine().begin() as c:
        c.execute(text(f"TRUNCATE {', '.join(Base.metadata.tables)} RESTART IDENTITY CASCADE"))
    yield
