"""Tests for tradingagents.cn_plugin.dataflows.tushare_provider."""
import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers to build mock DataFrames
# ---------------------------------------------------------------------------

def _daily_df():
    return pd.DataFrame({
        "ts_code": ["600519.SH", "600519.SH"],
        "trade_date": ["20250110", "20250109"],
        "open": [1800.0, 1790.0],
        "high": [1820.0, 1810.0],
        "low": [1795.0, 1785.0],
        "close": [1815.0, 1800.0],
        "vol": [50000.0, 48000.0],
    })


def _daily_basic_df():
    return pd.DataFrame({
        "ts_code": ["600519.SH"],
        "trade_date": ["20250110"],
        "pe": [35.2],
        "pb": [12.5],
        "total_mv": [2280000.0],
        "circ_mv": [2100000.0],
    })


def _stock_basic_df():
    return pd.DataFrame({
        "ts_code": ["600519.SH"],
        "name": ["贵州茅台"],
        "industry": ["白酒"],
        "area": ["贵州"],
        "list_date": ["20010827"],
    })


def _balancesheet_df():
    return pd.DataFrame({
        "ts_code": ["600519.SH"] * 4,
        "ann_date": ["20250101", "20241001", "20240701", "20240401"],
        "end_date": ["20241231", "20240930", "20240630", "20240331"],
        "total_assets": [1e11, 9e10, 8e10, 7e10],
        "total_liab": [2e10, 1.8e10, 1.6e10, 1.4e10],
        "total_hldr_eqy_exc_min_int": [8e10, 7.2e10, 6.4e10, 5.6e10],
        "money_cap": [5e10, 4.5e10, 4e10, 3.5e10],
        "accounts_receiv": [1e9, 9e8, 8e8, 7e8],
        "inventories": [2e9, 1.8e9, 1.6e9, 1.4e9],
    })


def _cashflow_df():
    return pd.DataFrame({
        "ts_code": ["600519.SH"] * 4,
        "ann_date": ["20250101", "20241001", "20240701", "20240401"],
        "end_date": ["20241231", "20240930", "20240630", "20240331"],
        "net_profit": [6e10, 5e10, 4e10, 3e10],
        "finan_exp": [1e8, 9e7, 8e7, 7e7],
        "c_fr_oper_a": [7e10, 6e10, 5e10, 4e10],
        "c_inf_fr_disp_subs_oper": [0, 0, 0, 0],
        "c_paid_goods_s": [1e10, 9e9, 8e9, 7e9],
        "n_cashflow_act": [6.5e10, 5.5e10, 4.5e10, 3.5e10],
        "n_cash_flows_fnc_act": [-1e10, -9e9, -8e9, -7e9],
    })


def _income_df():
    return pd.DataFrame({
        "ts_code": ["600519.SH"] * 4,
        "ann_date": ["20250101", "20241001", "20240701", "20240401"],
        "end_date": ["20241231", "20240930", "20240630", "20240331"],
        "total_revenue": [1.5e11, 1.2e11, 9e10, 6e10],
        "revenue": [1.4e11, 1.1e11, 8.5e10, 5.5e10],
        "total_cogs": [3e10, 2.5e10, 2e10, 1.5e10],
        "operate_profit": [8e10, 6.5e10, 5e10, 3.5e10],
        "total_profit": [8.2e10, 6.7e10, 5.2e10, 3.7e10],
        "income_tax": [2e10, 1.6e10, 1.2e10, 8e9],
        "n_income": [6.2e10, 5.1e10, 4e10, 2.9e10],
        "basic_eps": [49.3, 40.5, 31.8, 23.1],
    })


def _holdertrade_df():
    rows = 20
    return pd.DataFrame({
        "ts_code": ["600519.SH"] * rows,
        "ann_date": [f"2025010{i % 9 + 1}" for i in range(rows)],
        "holder_name": [f"Holder{i}" for i in range(rows)],
        "hold_amount": [1000 * (i + 1) for i in range(rows)],
        "change_type": ["增持" if i % 2 == 0 else "减持" for i in range(rows)],
    })


# ---------------------------------------------------------------------------
# Fixture: mock pro API
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_pro():
    """Return a MagicMock that mimics tushare.pro_api()."""
    pro = MagicMock()
    pro.daily.return_value = _daily_df()
    pro.daily_basic.return_value = _daily_basic_df()
    pro.stock_basic.return_value = _stock_basic_df()
    pro.balancesheet.return_value = _balancesheet_df()
    pro.cashflow.return_value = _cashflow_df()
    pro.income.return_value = _income_df()
    pro.stk_holdertrade.return_value = _holdertrade_df()
    return pro


@pytest.fixture()
def patch_provider(mock_pro):
    """Patch _get_pro() in the provider module and ensure token is set."""
    import tradingagents.cn_plugin.dataflows.tushare_provider as mod

    # Patch _get_pro to return our mock and ensure token check passes
    with patch.object(mod, "_get_pro", return_value=mock_pro):
        yield mod, mock_pro


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetStockData:
    def test_returns_csv_with_correct_columns(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert isinstance(result, str)
        # Header lines present
        assert "# Stock data for 600519.SH" in result
        assert "# Source: Tushare" in result
        # CSV columns present
        assert "Date,Open,High,Low,Close,Volume" in result
        # Data rows present
        lines = [l for l in result.splitlines() if not l.startswith("#") and l.strip()]
        assert len(lines) >= 2  # header row + at least 1 data row

    def test_empty_dataframe_returns_no_data(self, patch_provider):
        mod, mock_pro = patch_provider
        mock_pro.daily.return_value = pd.DataFrame()
        result = mod.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "No data" in result

    def test_date_format_normalised(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        # Dates in output should be YYYY-MM-DD, not YYYYMMDD
        assert "20250110" not in result
        assert "2025-01-10" in result or "2025-01-09" in result


class TestGetFundamentals:
    def test_returns_formatted_text_with_company_info(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_fundamentals("600519.SH")
        assert isinstance(result, str)
        assert "贵州茅台" in result
        assert "白酒" in result
        assert "PE Ratio" in result
        assert "PB Ratio" in result
        assert "# Data for 600519.SH" in result

    def test_empty_daily_basic_shows_fallback(self, patch_provider):
        mod, mock_pro = patch_provider
        mock_pro.daily_basic.return_value = pd.DataFrame()
        result = mod.get_fundamentals("600519.SH")
        assert "No valuation data available" in result

    def test_empty_stock_basic_shows_fallback(self, patch_provider):
        mod, mock_pro = patch_provider
        mock_pro.stock_basic.return_value = pd.DataFrame()
        result = mod.get_fundamentals("600519.SH")
        assert "No company info available" in result


class TestTokenValidation:
    def test_raises_value_error_when_token_empty(self):
        """Test that _get_pro raises ValueError when token is empty."""
        import tradingagents.cn_plugin.dataflows.tushare_provider as mod
        original_token = mod.CN_CONFIG.get("tushare_token", "")
        try:
            mod.CN_CONFIG["tushare_token"] = ""
            # Patch tushare module to avoid real import
            ts_mock = MagicMock()
            with patch.dict(sys.modules, {"tushare": ts_mock}):
                with pytest.raises(ValueError, match="TUSHARE_TOKEN not configured"):
                    mod._get_pro()
        finally:
            mod.CN_CONFIG["tushare_token"] = original_token

    def test_raises_value_error_for_get_stock_data_when_token_empty(self):
        """Test that get_stock_data raises ValueError when token is empty."""
        import tradingagents.cn_plugin.dataflows.tushare_provider as mod
        original_token = mod.CN_CONFIG.get("tushare_token", "")
        try:
            mod.CN_CONFIG["tushare_token"] = ""
            ts_mock = MagicMock()
            with patch.dict(sys.modules, {"tushare": ts_mock}):
                with pytest.raises(ValueError, match="TUSHARE_TOKEN not configured"):
                    mod.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        finally:
            mod.CN_CONFIG["tushare_token"] = original_token

    def test_raises_value_error_for_fundamentals_when_token_empty(self):
        """Test that get_fundamentals raises ValueError when token is empty."""
        import tradingagents.cn_plugin.dataflows.tushare_provider as mod
        original_token = mod.CN_CONFIG.get("tushare_token", "")
        try:
            mod.CN_CONFIG["tushare_token"] = ""
            ts_mock = MagicMock()
            with patch.dict(sys.modules, {"tushare": ts_mock}):
                with pytest.raises(ValueError, match="TUSHARE_TOKEN not configured"):
                    mod.get_fundamentals("600519.SH")
        finally:
            mod.CN_CONFIG["tushare_token"] = original_token


class TestFinancialStatements:
    def test_balance_sheet_returns_csv(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_balance_sheet("600519.SH")
        assert "# Data for 600519.SH" in result
        assert "total_assets" in result

    def test_cashflow_returns_csv(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_cashflow("600519.SH")
        assert "# Data for 600519.SH" in result
        assert "net_profit" in result

    def test_income_statement_returns_csv(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_income_statement("600519.SH")
        assert "# Data for 600519.SH" in result
        assert "total_revenue" in result

    def test_insider_transactions_returns_csv(self, patch_provider):
        mod, _ = patch_provider
        result = mod.get_insider_transactions("600519.SH")
        assert "# Data for 600519.SH" in result
        assert "holder_name" in result

    def test_balance_sheet_empty_returns_no_data(self, patch_provider):
        mod, mock_pro = patch_provider
        mock_pro.balancesheet.return_value = pd.DataFrame()
        result = mod.get_balance_sheet("600519.SH")
        assert "No balance sheet data available" in result
