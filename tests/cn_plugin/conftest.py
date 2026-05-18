"""Conftest for cn_plugin tests.

Pre-injects mock modules for heavy dataflows dependencies (yfinance, alpha_vantage, etc.)
so that tests can import tradingagents.cn_plugin without needing the full dependency tree.
"""
import sys
import types
from unittest.mock import MagicMock


def _noop(*args, **kwargs):
    return None


def _stub_dataflows_vendors():
    """Stub out vendor modules that require heavy optional deps (dateutil, etc.)."""

    # --- y_finance stub ---
    if "tradingagents.dataflows.y_finance" not in sys.modules:
        mod = types.ModuleType("tradingagents.dataflows.y_finance")
        for name in (
            "get_YFin_data_online",
            "get_stock_stats_indicators_window",
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_insider_transactions",
        ):
            setattr(mod, name, _noop)
        sys.modules["tradingagents.dataflows.y_finance"] = mod

    # --- yfinance_news stub ---
    if "tradingagents.dataflows.yfinance_news" not in sys.modules:
        mod = types.ModuleType("tradingagents.dataflows.yfinance_news")
        mod.get_news_yfinance = _noop
        mod.get_global_news_yfinance = _noop
        sys.modules["tradingagents.dataflows.yfinance_news"] = mod

    # --- alpha_vantage stub ---
    if "tradingagents.dataflows.alpha_vantage" not in sys.modules:
        mod = types.ModuleType("tradingagents.dataflows.alpha_vantage")
        for name in (
            "get_stock",
            "get_indicator",
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_insider_transactions",
            "get_news",
            "get_global_news",
        ):
            setattr(mod, name, _noop)
        sys.modules["tradingagents.dataflows.alpha_vantage"] = mod

    # --- alpha_vantage_common stub ---
    if "tradingagents.dataflows.alpha_vantage_common" not in sys.modules:
        mod = types.ModuleType("tradingagents.dataflows.alpha_vantage_common")

        class AlphaVantageRateLimitError(Exception):
            pass

        mod.AlphaVantageRateLimitError = AlphaVantageRateLimitError
        sys.modules["tradingagents.dataflows.alpha_vantage_common"] = mod


# Run at collection time so imports in test modules succeed
_stub_dataflows_vendors()
