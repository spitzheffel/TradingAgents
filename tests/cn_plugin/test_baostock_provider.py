"""Tests for tradingagents.cn_plugin.dataflows.baostock_provider."""
import sys
import types
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers: build mock BaoStock ResultSet objects
# ---------------------------------------------------------------------------

def _make_rs(rows: list[list], fields: list[str], error_code: str = "0"):
    """Build a mock BaoStock ResultSet that iterates over rows."""
    rs = MagicMock()
    rs.fields = fields
    rs.error_code = error_code

    # Simulate rs.next() advancing through rows, rs.get_row_data() returning current row
    _state = {"idx": -1}

    def _next():
        _state["idx"] += 1
        if _state["idx"] < len(rows):
            rs.error_code = "0"
            return True
        rs.error_code = "10007"  # end of data
        return False

    def _get_row():
        return rows[_state["idx"]]

    rs.next.side_effect = _next
    rs.get_row_data.side_effect = _get_row
    return rs


def _ohlcv_rs(n: int = 2):
    fields = ["date", "open", "high", "low", "close", "volume"]
    # Generate valid dates starting from 2024-01-02, stepping by 1 day each row
    base = pd.Timestamp("2024-01-02")
    rows = [
        [(base + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
         "1790.0", "1810.0", "1785.0", "1800.0", "48000"]
        for i in range(n)
    ]
    return _make_rs(rows, fields)


def _empty_rs():
    rs = MagicMock()
    rs.fields = ["date", "open", "high", "low", "close", "volume"]
    rs.error_code = "10007"
    rs.next.return_value = False
    return rs


def _basic_rs():
    fields = ["code", "code_name", "ipoDate", "outDate", "type", "status"]
    rows = [["sh.600519", "贵州茅台", "2001-08-27", "", "1", "1"]]
    return _make_rs(rows, fields)


def _financial_rs(n: int = 4):
    fields = ["code", "pubDate", "statDate", "totalAssets", "netProfit"]
    rows = [
        ["sh.600519", f"2024-{(4 - i) * 3:02d}-30", f"2024-{(4 - i) * 3:02d}-30",
         str(1e11 - i * 1e10), str(6e10 - i * 1e10)]
        for i in range(n)
    ]
    return _make_rs(rows, fields)


# ---------------------------------------------------------------------------
# Fixture: mock baostock module
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_baostock():
    """Inject a mock baostock module so no real network calls are made."""
    bs_mock = MagicMock()

    # login returns success by default
    login_result = MagicMock()
    login_result.error_code = "0"
    login_result.error_msg = ""
    bs_mock.login.return_value = login_result

    # logout is a no-op
    bs_mock.logout.return_value = None

    # default data responses
    bs_mock.query_history_k_data_plus.return_value = _ohlcv_rs()
    bs_mock.query_stock_basic.return_value = _basic_rs()
    bs_mock.query_balance_data.return_value = _financial_rs()
    bs_mock.query_cash_flow_data.return_value = _financial_rs()
    bs_mock.query_profit_data.return_value = _financial_rs()

    with patch.dict(sys.modules, {"baostock": bs_mock}):
        yield bs_mock


@pytest.fixture()
def provider():
    """Return the provider module (imported after baostock mock is in place)."""
    import importlib
    import tradingagents.cn_plugin.dataflows.baostock_provider as mod
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests: _to_bs_code
# ---------------------------------------------------------------------------

class TestToBsCode:
    def test_sh_conversion(self, provider):
        assert provider._to_bs_code("600519.SH") == "sh.600519"

    def test_sz_conversion(self, provider):
        assert provider._to_bs_code("000858.SZ") == "sz.000858"

    def test_already_bs_format_passthrough(self, provider):
        # If input has no dot-separated exchange suffix, return as-is
        result = provider._to_bs_code("sh600519")
        assert result == "sh600519"

    def test_lowercase_exchange(self, provider):
        assert provider._to_bs_code("600519.sh") == "sh.600519"


# ---------------------------------------------------------------------------
# Tests: _ensure_login / login error
# ---------------------------------------------------------------------------

class TestEnsureLogin:
    def test_login_success_does_not_raise(self, provider, mock_baostock):
        # Should not raise
        provider._ensure_login()
        mock_baostock.login.assert_called_once()

    def test_login_failure_raises_connection_error(self, provider, mock_baostock):
        fail_result = MagicMock()
        fail_result.error_code = "10001"
        fail_result.error_msg = "connection refused"
        mock_baostock.login.return_value = fail_result

        with pytest.raises(ConnectionError, match="BaoStock login failed"):
            provider._ensure_login()


# ---------------------------------------------------------------------------
# Tests: get_stock_data
# ---------------------------------------------------------------------------

class TestGetStockData:
    def test_returns_csv_with_correct_columns(self, provider):
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert isinstance(result, str)
        assert "# Stock data for 600519.SH" in result
        assert "# Source: BaoStock" in result
        assert "Date,Open,High,Low,Close,Volume" in result

    def test_data_rows_present(self, provider):
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        data_lines = [l for l in result.splitlines() if not l.startswith("#") and l.strip()]
        # header row + 2 data rows
        assert len(data_lines) >= 3

    def test_total_records_in_header(self, provider):
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "# Total records: 2" in result

    def test_empty_resultset_returns_no_data_message(self, provider, mock_baostock):
        mock_baostock.query_history_k_data_plus.return_value = _empty_rs()
        result = provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        assert "No data found for 600519.SH" in result

    def test_bs_code_passed_to_query(self, provider, mock_baostock):
        provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        call_args = mock_baostock.query_history_k_data_plus.call_args
        assert call_args.args[0] == "sh.600519"

    def test_adjustflag_is_qianfuquan(self, provider, mock_baostock):
        """adjustflag='2' means 前复权."""
        provider.get_stock_data("600519.SH", "2025-01-09", "2025-01-10")
        call_kwargs = mock_baostock.query_history_k_data_plus.call_args.kwargs
        assert call_kwargs.get("adjustflag") == "2"


# ---------------------------------------------------------------------------
# Tests: get_indicators
# ---------------------------------------------------------------------------

class TestGetIndicators:
    def test_returns_indicator_header(self, provider):
        result = provider.get_indicators("600519.SH", "2025-01-01", "2025-01-10")
        assert "# Technical Indicators for 600519.SH" in result
        assert "# Source: BaoStock" in result

    def test_indicator_names_present(self, provider, mock_baostock):
        # Provide enough rows for stockstats to compute indicators
        mock_baostock.query_history_k_data_plus.return_value = _ohlcv_rs(n=60)
        result = provider.get_indicators("600519.SH", "2025-01-01", "2025-03-01")
        assert "macd:" in result or "rsi_14:" in result or "boll:" in result

    def test_empty_resultset_returns_no_indicator_data(self, provider, mock_baostock):
        mock_baostock.query_history_k_data_plus.return_value = _empty_rs()
        result = provider.get_indicators("600519.SH", "2025-01-01", "2025-01-10")
        assert "No indicator data for 600519.SH" in result


# ---------------------------------------------------------------------------
# Tests: get_fundamentals
# ---------------------------------------------------------------------------

class TestGetFundamentals:
    def test_returns_formatted_text(self, provider):
        result = provider.get_fundamentals("600519.SH")
        assert isinstance(result, str)
        assert "# Fundamentals for 600519.SH" in result
        assert "# Source: BaoStock" in result

    def test_contains_stock_info(self, provider):
        result = provider.get_fundamentals("600519.SH")
        assert "贵州茅台" in result

    def test_empty_resultset_returns_no_data(self, provider, mock_baostock):
        mock_baostock.query_stock_basic.return_value = _empty_rs()
        result = provider.get_fundamentals("600519.SH")
        assert "No fundamentals data for 600519.SH" in result


# ---------------------------------------------------------------------------
# Tests: financial statements
# ---------------------------------------------------------------------------

class TestFinancialStatements:
    def test_balance_sheet_returns_csv(self, provider):
        result = provider.get_balance_sheet("600519.SH")
        assert "# Balance Sheet for 600519.SH" in result
        assert "# Source: BaoStock" in result

    def test_balance_sheet_limited_to_4_rows(self, provider, mock_baostock):
        mock_baostock.query_balance_data.return_value = _financial_rs(n=10)
        result = provider.get_balance_sheet("600519.SH")
        data_lines = [l for l in result.splitlines() if not l.startswith("#") and l.strip()]
        # 1 header row + 4 data rows
        assert len(data_lines) == 5

    def test_balance_sheet_empty_returns_no_data(self, provider, mock_baostock):
        mock_baostock.query_balance_data.return_value = _empty_rs()
        result = provider.get_balance_sheet("600519.SH")
        assert "No balance sheet data for 600519.SH" in result

    def test_cashflow_returns_csv(self, provider):
        result = provider.get_cashflow("600519.SH")
        assert "# Cash Flow for 600519.SH" in result

    def test_cashflow_empty_returns_no_data(self, provider, mock_baostock):
        mock_baostock.query_cash_flow_data.return_value = _empty_rs()
        result = provider.get_cashflow("600519.SH")
        assert "No cashflow data for 600519.SH" in result

    def test_income_statement_returns_csv(self, provider):
        result = provider.get_income_statement("600519.SH")
        assert "# Income Statement for 600519.SH" in result

    def test_income_statement_empty_returns_no_data(self, provider, mock_baostock):
        mock_baostock.query_profit_data.return_value = _empty_rs()
        result = provider.get_income_statement("600519.SH")
        assert "No income statement data for 600519.SH" in result

    def test_income_statement_limited_to_4_rows(self, provider, mock_baostock):
        mock_baostock.query_profit_data.return_value = _financial_rs(n=10)
        result = provider.get_income_statement("600519.SH")
        data_lines = [l for l in result.splitlines() if not l.startswith("#") and l.strip()]
        assert len(data_lines) == 5


# ---------------------------------------------------------------------------
# Tests: get_insider_transactions
# ---------------------------------------------------------------------------

class TestGetInsiderTransactions:
    def test_returns_unavailable_message(self, provider):
        result = provider.get_insider_transactions("600519.SH")
        assert "not available from BaoStock" in result
        assert "600519.SH" in result

    def test_does_not_call_baostock(self, provider, mock_baostock):
        provider.get_insider_transactions("600519.SH")
        mock_baostock.query_history_k_data_plus.assert_not_called()
        mock_baostock.query_stock_basic.assert_not_called()
