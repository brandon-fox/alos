# Plan 07 — PostgreSQL ORM & Migration Infrastructure

## Architecture & Design
1. **SQLAlchemy 2.0 ORM**: Define models with `Mapped[]` and `mapped_column()` syntax.
2. **Alembic Integration**: Configure `alembic/env.py` to import `alos.db.base.Base.metadata` so `alembic revision --autogenerate` accurately detects diffs.
3. **Database Manager**: `alos.db.session.DatabaseManager` will manage engine creation, sessionmaker binding, and transaction scope context managers.
4. **Automated Migration Verification**: Test suite will execute migration upgrades against an ephemeral test engine to guarantee migrations run cleanly without failure.
