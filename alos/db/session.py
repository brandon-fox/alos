"""Database session management and connection pooling for ALOS engine.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-006)
Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3602)
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from alos.config.settings import ALOSSettings
from alos.db.base import Base

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/n8n"


def _configure_sqlite_pragmas(dbapi_conn: Any, is_memory: bool) -> None:
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout=30000")
        if not is_memory:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


class DatabaseManager:
    """Manager for database engine creation, table management, and sessions."""

    def __init__(self, db_url: str | None = None) -> None:
        resolved_url = db_url or ALOSSettings().database_url
        is_sqlite = resolved_url.startswith("sqlite")
        connect_args: dict[str, Any] = {}
        if is_sqlite:
            connect_args = {"check_same_thread": False, "timeout": 30.0}

        self.engine = create_engine(resolved_url, connect_args=connect_args, pool_pre_ping=True)
        if is_sqlite:
            is_memory = ":memory:" in resolved_url
            event.listen(
                self.engine,
                "connect",
                lambda conn, _rec: _configure_sqlite_pragmas(conn, is_memory),
            )
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def create_all_tables(self) -> None:
        """Create all tables defined in Base metadata."""
        Base.metadata.create_all(bind=self.engine)

    def drop_all_tables(self) -> None:
        """Drop all tables defined in Base metadata."""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
