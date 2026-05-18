import pytest
from tradingagents.cn_plugin.ticker import normalize_ticker, is_china_ticker


class TestNormalizeTicker:
    @pytest.mark.parametrize("input_val,expected", [
        ("600519", "600519.SH"),
        ("600519.SH", "600519.SH"),
        ("600519.sh", "600519.SH"),
        ("SH600519", "600519.SH"),
        ("sh600519", "600519.SH"),
        ("000858", "000858.SZ"),
        ("000858.SZ", "000858.SZ"),
        ("SZ000858", "000858.SZ"),
        ("300750", "300750.SZ"),
        ("688981", "688981.SH"),
        ("830799", "830799.BJ"),
        ("830799.BJ", "830799.BJ"),
        ("BJ830799", "830799.BJ"),
    ])
    def test_china_tickers(self, input_val, expected):
        assert normalize_ticker(input_val) == expected

    @pytest.mark.parametrize("input_val", [
        "AAPL", "TSLA", "MSFT", "TSM", "BRK.B", "RELIANCE.NS",
    ])
    def test_non_china_passthrough(self, input_val):
        assert normalize_ticker(input_val) == input_val


class TestIsChinaTicker:
    @pytest.mark.parametrize("ticker,expected", [
        ("600519.SH", True),
        ("000858.SZ", True),
        ("830799.BJ", True),
        ("AAPL", False),
        ("9988.HK", False),
    ])
    def test_detection(self, ticker, expected):
        assert is_china_ticker(ticker) == expected
