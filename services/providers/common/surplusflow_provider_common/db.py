"""Shared SQLite engine for the marketplace and provider simulators.

Per `PROJECT_CONTEXT.md` section 8: "SQLite belongs only to the
marketplace/provider backend. Other services access it through HTTP and
must not open the database file directly." The marketplace and the seller
and courier simulators are all owned by Person 3, so they share one SQLite
file directly; the buyer agent and web app must go through HTTP.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _default_db_path() -> str:
    # db.py -> surplusflow_provider_common -> common -> providers -> services -> repo root
    root = Path(__file__).resolve().parents[4]
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


@contextlib.contextmanager
def startup_lock() -> Iterator[None]:
    """Serializes table creation and demo-data seeding across the six
    processes (marketplace, 3 sellers, 2 couriers) that start against the
    same SQLite file at roughly the same time. Without this, two processes
    can both see "table missing" / "no sellers yet" and race each other
    into a `CREATE TABLE` or duplicate-insert failure.
    """

    db_path = get_database_url().removeprefix("sqlite:///")
    # ".db" suffix so the root .gitignore's "*.db" pattern covers it too.
    lock_path = f"{db_path.removesuffix('.db')}.startup-lock.db"
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
