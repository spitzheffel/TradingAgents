"""Tests for cache_manager: make_cache_key, cache_get, cache_set."""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# make_cache_key
# ---------------------------------------------------------------------------

def test_make_cache_key_deterministic():
    from tradingagents.cn_plugin.cache.cache_manager import make_cache_key
    k1 = make_cache_key("get_stock_data", "000001.SZ", "2024-01-01")
    k2 = make_cache_key("get_stock_data", "000001.SZ", "2024-01-01")
    assert k1 == k2


def test_make_cache_key_different_inputs():
    from tradingagents.cn_plugin.cache.cache_manager import make_cache_key
    k1 = make_cache_key("get_stock_data", "000001.SZ")
    k2 = make_cache_key("get_stock_data", "600000.SH")
    assert k1 != k2


def test_make_cache_key_different_methods():
    from tradingagents.cn_plugin.cache.cache_manager import make_cache_key
    k1 = make_cache_key("get_stock_data", "000001.SZ")
    k2 = make_cache_key("get_news", "000001.SZ")
    assert k1 != k2


def test_make_cache_key_length():
    from tradingagents.cn_plugin.cache.cache_manager import make_cache_key
    key = make_cache_key("get_stock_data", "000001.SZ")
    assert len(key) == 32


# ---------------------------------------------------------------------------
# cache_get
# ---------------------------------------------------------------------------

def test_cache_get_returns_none_when_pool_none():
    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=None):
        from tradingagents.cn_plugin.cache.cache_manager import cache_get
        result = cache_get("somekey")
        assert result is None


def test_cache_get_returns_content_on_hit():
    """Row with fetched_at = yesterday → not subject to intraday TTL → return content."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    mock_row = ("cached_content", yesterday)

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=mock_pool):
        from tradingagents.cn_plugin.cache.cache_manager import cache_get
        result = cache_get("somekey")
        assert result == "cached_content"


def test_cache_get_returns_none_on_miss():
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = None

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=mock_pool):
        from tradingagents.cn_plugin.cache.cache_manager import cache_get
        result = cache_get("missingkey")
        assert result is None


def test_cache_get_returns_none_on_ttl_expiry():
    """Row fetched today but older than TTL → treat as miss."""
    # fetched_at = 20 minutes ago (TTL default = 15 min)
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    mock_row = ("stale_content", stale_time)

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=mock_pool):
        from tradingagents.cn_plugin.cache.cache_manager import cache_get
        result = cache_get("stalekey")
        assert result is None


def test_cache_get_returns_content_within_ttl():
    """Row fetched today within TTL → return content."""
    fresh_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    mock_row = ("fresh_content", fresh_time)

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = mock_row

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=mock_pool):
        from tradingagents.cn_plugin.cache.cache_manager import cache_get
        result = cache_get("freshkey")
        assert result == "fresh_content"


# ---------------------------------------------------------------------------
# cache_set
# ---------------------------------------------------------------------------

def test_cache_set_noop_when_pool_none():
    """cache_set should not raise and do nothing when pool is None."""
    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=None):
        from tradingagents.cn_plugin.cache.cache_manager import cache_set
        # Should not raise
        cache_set("somekey", "somevalue")


def test_cache_set_executes_upsert():
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=mock_pool):
        from tradingagents.cn_plugin.cache.cache_manager import cache_set
        cache_set("mykey", "myvalue")
        mock_cur.execute.assert_called_once()
        call_args = mock_cur.execute.call_args[0]
        assert "INSERT INTO data_cache" in call_args[0]
        assert call_args[1] == ("mykey", "myvalue")


# ---------------------------------------------------------------------------
# Integration: cache_set then cache_get returns value
# ---------------------------------------------------------------------------

def test_cache_roundtrip():
    """Simulate set then get using a shared in-memory store."""
    store = {}

    def fake_execute(sql, params=None):
        if params and "INSERT" in sql:
            store[params[0]] = params[1]
        elif params:
            # SELECT
            fake_execute._last_key = params[0]

    def fake_fetchone():
        key = getattr(fake_execute, "_last_key", None)
        if key and key in store:
            # Return content with a fresh timestamp (5 min ago)
            return (store[key], datetime.now(timezone.utc) - timedelta(minutes=5))
        return None

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.execute.side_effect = fake_execute
    mock_cur.fetchone.side_effect = fake_fetchone

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    with patch("tradingagents.cn_plugin.cache.cache_manager.get_pool", return_value=mock_pool):
        from tradingagents.cn_plugin.cache.cache_manager import cache_get, cache_set
        cache_set("roundtrip_key", "roundtrip_value")
        result = cache_get("roundtrip_key")
        assert result == "roundtrip_value"
