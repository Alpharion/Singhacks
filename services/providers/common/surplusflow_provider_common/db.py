"""Shared SQLite engine for the marketplace and provider simulators.

Per `PROJECT_CONTEXT.md` section 8: "SQLite belongs only to the
marketplace/provider backend. Other services access it through HTTP and
must not open the database file directly." The marketplace and the seller
and courier simulators are all owned by Person 3, so they share one SQLite
file directly; the buyer agent and web app must go through HTTP.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _default_db_path() -> str:
    root = Path(__file__).resolve().parents[3]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "surplusflow.db")


def get_database_url() -> str:
    configured = os.environ.get("SURPLUSFLOW_DB_PATH")
    path = configured if configured else _default_db_path()
    return f"sqlite:///{path}"


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
