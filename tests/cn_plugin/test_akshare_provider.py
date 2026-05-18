"""Tests for tradingagents.cn_plugin.dataflows.akshare_provider."""
import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers to build mock DataFrames
# ---------------------------------------------------------------------------

def _hist_df():
    """Simulate ak.stock_zh_a_hist() return value with Chinese column names."""
    return pd.DataFrame({
        "日期": ["2025-01-09", "2025-01-10"],
        "开盘": [1790.0, 1800.0],
        "收盘": [1800.0, 1815.0],
        "最高": [1810.0, 1820.0],
        "最低": [1785.0, 1795.0],
        "成交量": [48000.0, 50000.0],
        "成交额": [8.64e10, 9.075e10],
        "振幅": [1.39, 1.39],
        "涨跌幅": [0.56, 0.83],
        "涨跌额": [10.0, 15.0],
        "换手率": [0.38, 0.40],
    })


def _info_df():
    """Simulate ak.stock_individual_info_em() return value."""
    return pd.DataFrame({
        "item": ["股票代码", "股票简称", "行业", "上市时间"],
        "value": ["600519", "贵州茅台", "白酒", "2001-08-27"],
    })


def _financial_df(n=4):
    """Generic financial statement DataFrame."""
    return pd.DataFrame({
        "REPORT_DATE": [f"2024-{(4 - i) * 3:02d}-30" for i in range(n)],
        "TOTAL_ASSETS": [1e11 - i * 1e10 for i in range(n)],
        "NET_PROFIT": [6e10 - i * 1e10 for i in range(n)],
    })


def _insider_df(n=20):
    """Simulate ak.stock_hold_management_detail_em() return value."""
    return pd.DataFrame({
        "变动日期": [f"2025-01-{i + 1:02d}" for i in range(n)],
        "董监高姓名": [f"Manager{i}" for i in range(n)],
        "变动股数": [1000 * (i + 1) for i in range(n)],
        "变动类型": ["增持" if i % 2 == 0 else "减持" for i in range(n)],
    })


# ---------------------------------------------------------------------------
# Fixture: mock akshare module
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_akshare():
    """Inject a mock akshare module so no real network calls are made."""
    ak_mock = MagicMock()
    ak_mock.stock_zh_a_hist.return_value = _hist_df()
    ak_mock.stock_individual_info_em.return_value = _info_df()
    ak_mock.stock_balance_sheet_by_report_em.return_value = _financial_df()
    ak_mock.stock_cash_flow_sheet_by_report_em.return_value = _financial_df()
    ak_mock.stock_profit_sheet_by_report_em.return_value = _financial_df()
    ak_mock.stock_hold_management_detail_em.return_value = _insider_df()

    with patch.dict(sys.modules, {"akshare": ak_mock}):
        yield ak_mock


@pytest.fixture()
def provider():
    """Return the provider module (imported after akshare mock is in place)."""
    import importlib
    import tradingagents.cn_plugin.dataflows.akshare_provider as mod
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests: get_stock_data
# ---------------------------------------------------------------------------

class TestGetStockData:
    def test_returns_csv_with_correct_columns(self, provider):
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert isinstance(result, str)
        assert "# Stock data for 600519.SH" in result
        assert "# Source: AKShare" in result
        assert "Date,Open,High,Low,Close,Volume" in result

    def test_data_rows_present(self, provider):
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        data_lines = [l for l in result.splitlines() if not l.startswith("#") and l.strip()]
        # header row + 2 data rows
        assert len(data_lines) >= 3

    def test_total_records_in_header(self, provider):
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "# Total records: 2" in result

    def test_empty_dataframe_returns_no_data_message(self, provider, mock_akshare):
        mock_akshare.stock_zh_a_hist.return_value = pd.DataFrame()
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "No data found for 600519.SH" in result

    def test_none_dataframe_returns_no_data_message(self, provider, mock_akshare):
        mock_akshare.stock_zh_a_hist.return_value = None
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "No data found for 600519.SH" in result

    def test_extracts_code_from_dotted_symbol(self, provider, mock_akshare):
        provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        call_kwargs = mock_akshare.stock_zh_a_hist.call_args
        # symbol passed to AKShare should be bare 6-digit code
        assert call_kwargs.kwargs.get("symbol") == "600519" or (
            call_kwargs.args and call_kwargs.args[0] == "600519"
        )

    def test_date_format_is_yyyymmdd_for_akshare(self, provider, mock_akshare):
        """AKShare expects YYYYMMDD, not YYYY-MM-DD."""
        provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        call_kwargs = mock_akshare.stock_zh_a_hist.call_args
        start = call_kwargs.kwargs.get("start_date", "")
        end = call_kwargs.kwargs.get("end_date", "")
        assert "-" not in start
        assert "-" not in end

    def test_exception_returns_no_data_message(self, provider, mock_akshare):
        mock_akshare.stock_zh_a_hist.side_effect = Exception("network error")
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "No data found for 600519.SH" in result


# ---------------------------------------------------------------------------
# Tests: get_indicators
# ---------------------------------------------------------------------------

class TestGetIndicators:
    def test_returns_indicator_header(self, provider):
        result = provider.get_indicators("600519.SH", "2025-01-09", "2025-01-10")
        assert "# Technical Indicators for 600519.SH" in result
        assert "# Source: AKShare" in result

    def test_indicator_names_present(self, provider):
        result = provider.get_indicators("600519.SH", "2025-01-09", "2025-01-10")
        # At least some indicators should appear
        assert "macd:" in result or "rsi_14:" in result or "boll:" in result

    def test_empty_dataframe_returns_no_indicator_data(self, provider, mock_akshare):
        mock_akshare.stock_zh_a_hist.return_value = pd.DataFrame()
        result = provider.get_indicators("600519.SH", "2025-01-09", "2025-01-10")
        assert "No indicator data for 600519.SH" in result

    def test_exception_returns_no_indicator_data(self, provider, mock_akshare):
        mock_akshare.stock_zh_a_hist.side_effect = Exception("timeout")
        result = provider.get_indicators("600519.SH", "2025-01-09", "2025-01-10")
        assert "No indicator data for 600519.SH" in result


# ---------------------------------------------------------------------------
# Tests: get_fundamentals
# ---------------------------------------------------------------------------

class TestGetFundamentals:
    def test_returns_formatted_text(self, provider):
        result = provider.get_fundamentals("600519.SH")
        assert isinstance(result, str)
        assert "# Fundamentals for 600519.SH" in result
        assert "# Source: AKShare" in result

    def test_contains_info_items(self, provider):
        result = provider.get_fundamentals("600519.SH")
        assert "贵州茅台" in result
        assert "白酒" in result

    def test_empty_dataframe_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_individual_info_em.return_value = pd.DataFrame()
        result = provider.get_fundamentals("600519.SH")
        assert "No fundamentals data for 600519.SH" in result

    def test_none_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_individual_info_em.return_value = None
        result = provider.get_fundamentals("600519.SH")
        assert "No fundamentals data for 600519.SH" in result

    def test_exception_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_individual_info_em.side_effect = Exception("api error")
        result = provider.get_fundamentals("600519.SH")
        assert "No fundamentals data for 600519.SH" in result


# ---------------------------------------------------------------------------
# Tests: financial statements
# ---------------------------------------------------------------------------

class TestFinancialStatements:
    def test_balance_sheet_returns_csv(self, provider):
        result = provider.get_balance_sheet("600519.SH")
        assert "# Balance Sheet for 600519.SH" in result
        assert "REPORT_DATE" in result or "TOTAL_ASSETS" in result

    def test_balance_sheet_empty_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_balance_sheet_by_report_em.return_value = pd.DataFrame()
        result = provider.get_balance_sheet("600519.SH")
        assert "No balance sheet data for 600519.SH" in result

    def test_balance_sheet_exception_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_balance_sheet_by_report_em.side_effect = Exception("err")
        result = provider.get_balance_sheet("600519.SH")
        assert "No balance sheet data for 600519.SH" in result

    def test_cashflow_returns_csv(self, provider):
        result = provider.get_cashflow("600519.SH")
        assert "# Cash Flow for 600519.SH" in result

    def test_cashflow_empty_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_cash_flow_sheet_by_report_em.return_value = pd.DataFrame()
        result = provider.get_cashflow("600519.SH")
        assert "No cashflow data for 600519.SH" in result

    def test_cashflow_exception_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_cash_flow_sheet_by_report_em.side_effect = Exception("err")
        result = provider.get_cashflow("600519.SH")
        assert "No cashflow data for 600519.SH" in result

    def test_income_statement_returns_csv(self, provider):
        result = provider.get_income_statement("600519.SH")
        assert "# Income Statement for 600519.SH" in result

    def test_income_statement_empty_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_profit_sheet_by_report_em.return_value = pd.DataFrame()
        result = provider.get_income_statement("600519.SH")
        assert "No income statement data for 600519.SH" in result

    def test_income_statement_exception_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_profit_sheet_by_report_em.side_effect = Exception("err")
        result = provider.get_income_statement("600519.SH")
        assert "No income statement data for 600519.SH" in result

    def test_insider_transactions_returns_csv(self, provider):
        result = provider.get_insider_transactions("600519.SH")
        assert "# Insider Transactions for 600519.SH" in result
        assert "Manager" in result

    def test_insider_transactions_empty_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_hold_management_detail_em.return_value = pd.DataFrame()
        result = provider.get_insider_transactions("600519.SH")
        assert "No insider transaction data for 600519.SH" in result

    def test_insider_transactions_exception_returns_no_data(self, provider, mock_akshare):
        mock_akshare.stock_hold_management_detail_em.side_effect = Exception("err")
        result = provider.get_insider_transactions("600519.SH")
        assert "No insider transaction data for 600519.SH" in result

    def test_balance_sheet_limited_to_4_rows(self, provider, mock_akshare):
        mock_akshare.stock_balance_sheet_by_report_em.return_value = _financial_df(n=10)
        result = provider.get_balance_sheet("600519.SH")
        # CSV should have header + 4 data rows
        data_lines = [l for l in result.splitlines() if not l.startswith("#") and l.strip()]
        assert len(data_lines) == 5  # 1 header + 4 rows
