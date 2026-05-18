"""PostgreSQL connection pool management."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_pool = None


def get_pool():
    """Get or create the connection pool. Returns None if PG is unavailable."""
    global _pool
    if _pool is not None:
        return _pool

    from tradingagents.cn_plugin.config import CN_CONFIG
    dsn = CN_CONFIG.get("pg_dsn", "")
    if not dsn:
        return None

    try:
        import psycopg_pool
        _pool = psycopg_pool.ConnectionPool(dsn, min_size=1, max_size=5, open=True)
        return _pool
    except Exception as e:
        logger.warning(f"Failed to create PG connection pool: {e}")
        return None


def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
