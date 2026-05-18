"""China data provider — fallback chain orchestrator."""
from tradingagents.cn_plugin.config import CN_CONFIG


def _get_news_china(ticker, start_date, end_date):
    """Fetch news with eastmoney as primary, sina as fallback."""
    from tradingagents.cn_plugin.dataflows import eastmoney_news, sina_news
    try:
        result = eastmoney_news.get_news(ticker, start_date, end_date)
        if result and "No news" not in result:
            return result
    except Exception:
        pass
    try:
        return sina_news.get_news(ticker, start_date, end_date)
    except Exception:
        return f"No news available for {ticker}"


def _get_global_news_china(curr_date, look_back_days=None, limit=None):
    """Fetch global news from Chinese sources."""
    from tradingagents.cn_plugin.dataflows import eastmoney_news
    return eastmoney_news.get_global_news(curr_date, look_back_days, limit)


def route_china(method: str, *args, **kwargs) -> str:
    """Route to China-specific provider with fallback chain."""
    # Special routing for news methods
    if method == "get_news":
        return _get_news_china(*args, **kwargs)
    if method == "get_global_news":
        return _get_global_news_china(*args, **kwargs)

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
