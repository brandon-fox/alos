# Requirements Checklist: Database & ORM Evolution (Spec 10)

- [ ] Database models strictly use `Mapped[T]` annotations.
- [ ] Migration revisions generated cleanly via `alembic revision --autogenerate`.
- [ ] PostgreSQL connection pool handles async concurrency without leaks.
