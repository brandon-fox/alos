"""Hexagonal Ring 3 SQLAlchemy Unit of Work adapter for transactional persistence."""

from alos.db.session import DatabaseManager


class SqlAlchemyUnitOfWork(DatabaseManager):
    """Driven Unit of Work managing SQLAlchemy sessions, transactions, and pool disposal."""
