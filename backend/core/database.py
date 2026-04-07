"""
Database connection pool.
Call init_db() on startup, close_db() on shutdown.
Use get_db() as a FastAPI dependency for request-scoped connections.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

# Module-level pool (initialised once at startup)
_pool: pg_pool.ThreadedConnectionPool | None = None


def init_db() -> None:
    global _pool
    _pool = pg_pool.ThreadedConnectionPool(
        minconn=settings.TIMESCALE_POOL_MIN,
        maxconn=settings.TIMESCALE_POOL_MAX,
        host=settings.TIMESCALE_HOST,
        port=settings.TIMESCALE_PORT,
        dbname=settings.TIMESCALE_DB,
        user=settings.TIMESCALE_USER,
        password=settings.TIMESCALE_PASSWORD,
        cursor_factory=RealDictCursor,   # rows come back as dicts automatically
    )
    logger.info("TimescaleDB pool ready (%d–%d conns)",
                settings.TIMESCALE_POOL_MIN, settings.TIMESCALE_POOL_MAX)


def close_db() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        logger.info("TimescaleDB pool closed.")


def get_pool() -> pg_pool.ThreadedConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db() first.")
    return _pool


# ── Sync helper (for background tasks / services) ─────────────────────────────

def query_sync(sql: str, params=None) -> list[dict]:
    """Execute a SELECT and return rows as a list of dicts."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        get_pool().putconn(conn)


def execute_sync(sql: str, params=None) -> None:
    """Execute INSERT/UPDATE/DELETE."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        get_pool().putconn(conn)


# ── Async helper (wraps sync pool in a thread executor) ──────────────────────

async def query_async(sql: str, params=None) -> list[dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, query_sync, sql, params)


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_db():
    """
    Yields a psycopg2 connection from the pool.
    Commits on clean exit, rolls back on exception.
    """
    conn = get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        get_pool().putconn(conn)
