"""China data provider — fallback chain orchestrator."""
from tradingagents.cn_plugin.config import CN_CONFIG


def route_china(method: str, *args, **kwargs) -> str:
    """Route to China-specific provider with fallback chain."""
    # Lazy imports to avoid circular deps and missing optional deps
    from tradingagents.cn_plugin.dataflows import tushare_provider, akshare_provider, baostock_provider

    _PROVIDER_MAP = {
        "tushare": tushare_provider,
        "akshare": akshare_provider,
        "baostock": baostock_provider,
    }

    priority = CN_CONFIG.get("china_data_priority", ["tushare", "akshare", "baostock"])

    for provider_name in priority:
        provider = _PROVIDER_MAP.get(provider_name)
        if provider is None:
            continue
        func = getattr(provider, method, None)
        if func is None:
            continue
        try:
            result = func(*args, **kwargs)
            if result and "No data" not in str(result):
                return result
        except Exception:
            continue

    symbol = args[0] if args else "unknown"
    return f"No data available for {symbol} from any China data source"
