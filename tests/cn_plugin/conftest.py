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


def _stub_langchain():
    """Stub out langchain_core so cn_plugin/__init__.py can import agent_utils."""
    if "langchain_core" not in sys.modules:
        lc = types.ModuleType("langchain_core")
        sys.modules["langchain_core"] = lc

    if "langchain_core.messages" not in sys.modules:
        msgs = types.ModuleType("langchain_core.messages")
        msgs.HumanMessage = MagicMock
        msgs.RemoveMessage = MagicMock
        sys.modules["langchain_core.messages"] = msgs

    # Stub the full agents.utils.agent_utils so cn_plugin/__init__.py can patch it
    if "tradingagents.agents" not in sys.modules:
        agents_pkg = types.ModuleType("tradingagents.agents")
        sys.modules["tradingagents.agents"] = agents_pkg

    if "tradingagents.agents.utils" not in sys.modules:
        utils_pkg = types.ModuleType("tradingagents.agents.utils")
        sys.modules["tradingagents.agents.utils"] = utils_pkg

    if "tradingagents.agents.utils.agent_utils" not in sys.modules:
        agent_utils = types.ModuleType("tradingagents.agents.utils.agent_utils")
        agent_utils.get_language_instruction = lambda: "Respond in English."
        agent_utils.create_msg_delete = MagicMock
        sys.modules["tradingagents.agents.utils.agent_utils"] = agent_utils


# Run at collection time so imports in test modules succeed
_stub_dataflows_vendors()
_stub_langchain()
