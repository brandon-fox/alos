# Task Breakdown: Database & ORM Evolution (Spec 10)

- [ ] Task 1: Refactor models in `alos/db/models.py` to use SQLAlchemy 2.0 `Mapped[T]`.
- [ ] Task 2: Enable `pgvector` vector extension in Alembic migration scripts.
- [ ] Task 3: Configure `asyncpg` connection pooling in `alos/db/session.py`.
- [ ] Task 4: Add ORM `@listens_for(Base, "before_update")` timestamp event triggers.
