"""Route enhancement: ticker normalization + China market interception."""
import tradingagents.dataflows.interface as _iface
from tradingagents.cn_plugin.ticker import normalize_ticker, is_china_ticker

_original_route_to_vendor = _iface.route_to_vendor

_TICKER_FIRST_METHODS = {
    "get_stock_data", "get_indicators", "get_fundamentals",
    "get_balance_sheet", "get_cashflow", "get_income_statement",
    "get_news", "get_insider_transactions",
}


def _enhanced_route_to_vendor(method: str, *args, **kwargs):
    """Wrap route_to_vendor: normalize ticker, cache, force china vendor for A-share."""
    from tradingagents.cn_plugin.config import CN_CONFIG

    # Normalize ticker if applicable
    if method in _TICKER_FIRST_METHODS and args:
        normalized = normalize_ticker(args[0])
        args = (normalized,) + args[1:]

        # Force china vendor for A-share tickers
        if is_china_ticker(normalized):
            # Check cache first
            if CN_CONFIG.get("cache_enabled"):
                from tradingagents.cn_plugin.cache.cache_manager import make_cache_key, cache_get, cache_set
                key = make_cache_key(method, *args)
                cached = cache_get(key)
                if cached is not None:
                    return cached

            from tradingagents.cn_plugin.dataflows.provider import route_china
            result = route_china(method, *args, **kwargs)

            # Write to cache
            if CN_CONFIG.get("cache_enabled") and result and "No data" not in str(result):
                from tradingagents.cn_plugin.cache.cache_manager import make_cache_key, cache_set
                key = make_cache_key(method, *args)
                cache_set(key, result)

            return result

    # Non-china path: also cache if enabled
    if CN_CONFIG.get("cache_enabled") and method in _TICKER_FIRST_METHODS:
        from tradingagents.cn_plugin.cache.cache_manager import make_cache_key, cache_get, cache_set
        key = make_cache_key(method, *args)
        cached = cache_get(key)
        if cached is not None:
            return cached

        result = _original_route_to_vendor(method, *args, **kwargs)

        if result and "No data" not in str(result):
            cache_set(key, result)
        return result

    return _original_route_to_vendor(method, *args, **kwargs)


def patch_routing():
    """Monkey-patch route_to_vendor in the interface module."""
    _iface.route_to_vendor = _enhanced_route_to_vendor


def unpatch_routing():
    """Restore original route_to_vendor (for testing)."""
    _iface.route_to_vendor = _original_route_to_vendor
