"""PostgreSQL/pgvector connection pool (ADR01)."""

import asyncpg
from pgvector.asyncpg import register_vector

from .config import get_settings

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    # The project's Supabase pgvector extension is installed in public.
    for schema in ("public", None, "extensions"):
        try:
            if schema:
                await register_vector(conn, schema=schema)
            else:
                await register_vector(conn)
            break
        except Exception:
            continue



async def connect() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        kwargs = {
            "dsn": settings.database_url,
            "min_size": 1,
            "max_size": 10,
            "statement_cache_size": 0,
            "init": _init_connection,
        }
        if "supabase" in settings.database_url:
            kwargs["ssl"] = "require"
        _pool = await asyncpg.create_pool(**kwargs)

    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call connect() on startup.")
    return _pool
