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
    """Wrap route_to_vendor: normalize ticker, force china vendor for A-share."""
    if method in _TICKER_FIRST_METHODS and args:
        normalized = normalize_ticker(args[0])
        args = (normalized,) + args[1:]
        if is_china_ticker(normalized):
            from tradingagents.cn_plugin.dataflows.provider import route_china
            return route_china(method, *args, **kwargs)
    return _original_route_to_vendor(method, *args, **kwargs)


def patch_routing():
    """Monkey-patch route_to_vendor in the interface module."""
    _iface.route_to_vendor = _enhanced_route_to_vendor


def unpatch_routing():
    """Restore original route_to_vendor (for testing)."""
    _iface.route_to_vendor = _original_route_to_vendor
