"""Cache read/write logic with TTL support."""
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from tradingagents.cn_plugin.cache.pg_client import get_pool
from tradingagents.cn_plugin.config import CN_CONFIG

logger = logging.getLogger(__name__)


def make_cache_key(method: str, *args) -> str:
    """Create a deterministic cache key from method name + arguments."""
    raw = f"{method}:" + ":".join(str(a) for a in args)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def cache_get(key: str) -> Optional[str]:
    """Read from cache. Returns None on miss or if PG unavailable."""
    pool = get_pool()
    if pool is None:
        return None

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content, fetched_at FROM data_cache WHERE cache_key = %s",
                    (key,)
                )
                row = cur.fetchone()
                if row is None:
                    return None

                content, fetched_at = row

                # Check TTL for intraday data
                ttl_minutes = CN_CONFIG.get("cache_ttl_intraday_minutes", 15)
                now = datetime.now(timezone.utc)
                if fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=timezone.utc)

                # If data is from today and older than TTL, treat as miss
                if fetched_at.date() == now.date():
                    if (now - fetched_at) > timedelta(minutes=ttl_minutes):
                        return None

                return content
    except Exception as e:
        logger.debug(f"Cache read failed for {key}: {e}")
        return None


def cache_set(key: str, value: str) -> None:
    """Write to cache. Silent no-op if PG unavailable."""
    pool = get_pool()
    if pool is None:
        return

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO data_cache (cache_key, content, fetched_at)
                       VALUES (%s, %s, NOW())
                       ON CONFLICT (cache_key) DO UPDATE SET content = EXCLUDED.content, fetched_at = NOW()""",
                    (key, value)
                )
            conn.commit()
    except Exception as e:
        logger.debug(f"Cache write failed for {key}: {e}")
