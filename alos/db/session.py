"""Database session management and connection pooling for ALOS engine."""

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alos.db.base import Base

DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/n8n"
)


class DatabaseManager:
    """Manager for database engine creation, table management, and sessions."""

    def __init__(self, db_url: str = DEFAULT_DB_URL) -> None:
        # SQLite in-memory or file needs specific connection args for threading in tests
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self.engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
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
