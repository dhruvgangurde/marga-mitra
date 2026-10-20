from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.tables import Base


@lru_cache
def engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@contextmanager
def session() -> Iterator[Session]:
    """One transaction: commit on success, roll back on error."""
    with Session(engine(), expire_on_commit=False) as s, s.begin():
        yield s


def init_db() -> None:
    with engine().begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    # shortcut: no migrations, create_all at startup; add Alembic once the schema must change with data in it
    Base.metadata.create_all(engine())


def db_ok() -> bool:
    try:
        with engine().connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
