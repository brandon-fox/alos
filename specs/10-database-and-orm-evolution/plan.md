# Architecture Plan: Database & ORM Evolution (Spec 10)

```mermaid
graph TD
    App[ALOS Services] --> ORM[SQLAlchemy 2.0 Mapped Models]
    ORM --> Pool[asyncpg Connection Pool]
    Pool --> DB[(PostgreSQL + pgvector)]
    App --> Analytics[DuckDB / Polars Engine]
```

- Migrate `alos/db/models.py` to `Mapped[T]` syntax.
- Add `pgvector` HNSW indexes for embedding search.
- Configure `asyncpg` engine connection pools.
