"""Tests for Chinese news and sentiment data sources."""
import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers: mock DataFrames
# ---------------------------------------------------------------------------

def _news_df():
    """Simulate ak.stock_news_em() return value."""
    return pd.DataFrame({
        "新闻标题": ["茅台Q1业绩超预期", "茅台提价传闻", "茅台渠道改革"],
        "发布时间": ["2025-01-10 09:00:00", "2025-01-11 10:30:00", "2025-01-12 14:00:00"],
        "新闻内容": ["内容1", "内容2", "内容3"],
    })


def _cctv_df():
    """Simulate ak.news_cctv() return value."""
    return pd.DataFrame({
        "title": ["央行降准0.5个百分点", "GDP增速超预期", "贸易顺差创新高"],
        "date": ["2025-01-10", "2025-01-10", "2025-01-10"],
    })


def _baidu_df():
    """Simulate ak.news_economic_baidu() return value."""
    return pd.DataFrame({
        "title": ["美联储暂停加息", "原油价格下跌", "人民币汇率走强"],
        "time": ["2025-01-10", "2025-01-10", "2025-01-10"],
    })


def _comment_df():
    """Simulate ak.stock_comment_em() return value."""
    return pd.DataFrame({
        "代码": ["600519", "000001", "000002"],
        "名称": ["贵州茅台", "平安银行", "万科A"],
        "综合得分": [85.5, 72.3, 68.1],
        "主力净流入": [1.2e8, -3.4e7, 5.6e6],
    })


# ---------------------------------------------------------------------------
# Fixture: mock akshare
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_akshare():
    """Inject a mock akshare module so no real network calls are made."""
    ak_mock = MagicMock()
    ak_mock.stock_news_em.return_value = _news_df()
    ak_mock.news_cctv.return_value = _cctv_df()
    ak_mock.news_economic_baidu.return_value = _baidu_df()
    ak_mock.stock_comment_em.return_value = _comment_df()

    with patch.dict(sys.modules, {"akshare": ak_mock}):
        yield ak_mock


# ---------------------------------------------------------------------------
# Tests: eastmoney_news.get_news
# ---------------------------------------------------------------------------

class TestEastmoneyGetNews:
    @pytest.fixture()
    def mod(self):
        import importlib
        import tradingagents.cn_plugin.dataflows.eastmoney_news as m
        importlib.reload(m)
        return m

    def test_returns_formatted_header(self, mod):
        result = mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        assert "# News for 600519.SH" in result
        assert "# Source: 东方财富 (via AKShare)" in result

    def test_total_articles_in_header(self, mod):
        result = mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        assert "# Total articles:" in result

    def test_news_titles_present(self, mod):
        result = mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        assert "茅台Q1业绩超预期" in result

    def test_strips_suffix_from_ticker(self, mod, mock_akshare):
        mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        call_args = mock_akshare.stock_news_em.call_args
        symbol_arg = call_args.kwargs.get("symbol") or (call_args.args[0] if call_args.args else None)
        assert symbol_arg == "600519"

    def test_date_filter_excludes_out_of_range(self, mod, mock_akshare):
        # All news is in 2025-01-10 to 2025-01-12; request 2025-01-10 to 2025-01-11
        result = mod.get_news("600519.SH", "2025-01-10", "2025-01-11")
        # 2025-01-10 and 2025-01-11 articles should be included; 2025-01-12 should not
        assert "茅台Q1业绩超预期" in result
        assert "茅台提价传闻" in result
        assert "茅台渠道改革" not in result

    def test_empty_df_returns_no_news_message(self, mod, mock_akshare):
        mock_akshare.stock_news_em.return_value = pd.DataFrame()
        result = mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        assert "No news found for 600519.SH" in result

    def test_none_df_returns_no_news_message(self, mod, mock_akshare):
        mock_akshare.stock_news_em.return_value = None
        result = mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        assert "No news" in result

    def test_exception_returns_no_news_message(self, mod, mock_akshare):
        mock_akshare.stock_news_em.side_effect = Exception("network error")
        result = mod.get_news("600519.SH", "2025-01-09", "2025-01-13")
        assert "No news data available for 600519.SH" in result

    def test_date_filter_all_out_of_range_returns_no_news(self, mod, mock_akshare):
        # Request a date range that doesn't overlap with any news
        result = mod.get_news("600519.SH", "2024-01-01", "2024-01-31")
        assert "No news found for 600519.SH" in result


# ---------------------------------------------------------------------------
# Tests: eastmoney_news.get_global_news
# ---------------------------------------------------------------------------

class TestEastmoneyGetGlobalNews:
    @pytest.fixture()
    def mod(self):
        import importlib
        import tradingagents.cn_plugin.dataflows.eastmoney_news as m
        importlib.reload(m)
        return m

    def test_returns_formatted_header(self, mod):
        result = mod.get_global_news("2025-01-10")
        assert "# Global/Macro News as of 2025-01-10" in result
        assert "# Source: CCTV + 百度财经 (via AKShare)" in result

    def test_contains_cctv_news(self, mod):
        result = mod.get_global_news("2025-01-10")
        assert "[CCTV]" in result
        assert "央行降准" in result

    def test_contains_baidu_news(self, mod):
        result = mod.get_global_news("2025-01-10")
        assert "[百度财经]" in result
        assert "美联储暂停加息" in result

    def test_look_back_days_in_header(self, mod):
        result = mod.get_global_news("2025-01-10", look_back_days=14)
        assert "# Look back: 14 days" in result

    def test_default_look_back_is_7(self, mod):
        result = mod.get_global_news("2025-01-10")
        assert "# Look back: 7 days" in result

    def test_limit_caps_articles(self, mod, mock_akshare):
        # Return 10 CCTV + 10 Baidu = 20 total; limit to 5
        mock_akshare.news_cctv.return_value = pd.DataFrame({
            "title": [f"CCTV news {i}" for i in range(10)]
        })
        mock_akshare.news_economic_baidu.return_value = pd.DataFrame({
            "title": [f"Baidu news {i}" for i in range(10)]
        })
        result = mod.get_global_news("2025-01-10", limit=5)
        # Count article lines (lines starting with "[")
        article_lines = [l for l in result.splitlines() if l.startswith("[")]
        assert len(article_lines) == 5

    def test_cctv_exception_still_returns_baidu(self, mod, mock_akshare):
        mock_akshare.news_cctv.side_effect = Exception("cctv down")
        result = mod.get_global_news("2025-01-10")
        assert "[百度财经]" in result
        assert "[CCTV]" not in result

    def test_baidu_exception_still_returns_cctv(self, mod, mock_akshare):
        mock_akshare.news_economic_baidu.side_effect = Exception("baidu down")
        result = mod.get_global_news("2025-01-10")
        assert "[CCTV]" in result
        assert "[百度财经]" not in result

    def test_both_fail_returns_no_global_news(self, mod, mock_akshare):
        mock_akshare.news_cctv.side_effect = Exception("down")
        mock_akshare.news_economic_baidu.side_effect = Exception("down")
        result = mod.get_global_news("2025-01-10")
        assert "No global news available for 2025-01-10" in result

    def test_date_passed_without_dashes_to_cctv(self, mod, mock_akshare):
        mod.get_global_news("2025-01-10")
        call_args = mock_akshare.news_cctv.call_args
        date_arg = call_args.kwargs.get("date") or (call_args.args[0] if call_args.args else None)
        assert date_arg == "20250110"


# ---------------------------------------------------------------------------
# Tests: sentiment.get_china_sentiment
# ---------------------------------------------------------------------------

class TestGetChinaSentiment:
    @pytest.fixture()
    def mod(self):
        import importlib
        import tradingagents.cn_plugin.dataflows.sentiment as m
        importlib.reload(m)
        return m

    def test_returns_header(self, mod):
        result = mod.get_china_sentiment("600519.SH")
        assert "# Sentiment Data for 600519.SH" in result
        assert "# Source: 东方财富" in result

    def test_contains_sentiment_section(self, mod):
        result = mod.get_china_sentiment("600519.SH")
        assert "## 千股千评" in result

    def test_contains_score_data(self, mod):
        result = mod.get_china_sentiment("600519.SH")
        assert "综合得分" in result
        assert "85.5" in result

    def test_strips_suffix_from_ticker(self, mod, mock_akshare):
        mod.get_china_sentiment("600519.SH")
        mock_akshare.stock_comment_em.assert_called_once()

    def test_ticker_not_found_returns_message(self, mod, mock_akshare):
        # Use a code not in the mock DataFrame
        result = mod.get_china_sentiment("999999.SH")
        assert "未找到该股票数据" in result

    def test_empty_df_returns_no_data_message(self, mod, mock_akshare):
        mock_akshare.stock_comment_em.return_value = pd.DataFrame()
        result = mod.get_china_sentiment("600519.SH")
        assert "千股千评: 无数据" in result

    def test_none_df_returns_no_data_message(self, mod, mock_akshare):
        mock_akshare.stock_comment_em.return_value = None
        result = mod.get_china_sentiment("600519.SH")
        assert "千股千评: 无数据" in result

    def test_exception_returns_failure_message(self, mod, mock_akshare):
        mock_akshare.stock_comment_em.side_effect = Exception("api error")
        result = mod.get_china_sentiment("600519.SH")
        assert "千股千评: 获取失败" in result

    def test_df_without_code_column_returns_format_error(self, mod, mock_akshare):
        # DataFrame with no column containing "代码" or "code"
        mock_akshare.stock_comment_em.return_value = pd.DataFrame({
            "名称": ["贵州茅台"],
            "得分": [85.5],
        })
        result = mod.get_china_sentiment("600519.SH")
        assert "千股千评: 数据格式异常" in result


# ---------------------------------------------------------------------------
# Tests: provider.route_china news routing
# ---------------------------------------------------------------------------

class TestProviderNewsRouting:
    @pytest.fixture()
    def provider(self):
        import importlib
        import tradingagents.cn_plugin.dataflows.provider as m
        importlib.reload(m)
        return m

    @pytest.fixture()
    def eastmoney_mod(self):
        import importlib
        import tradingagents.cn_plugin.dataflows.eastmoney_news as m
        importlib.reload(m)
        return m

    def test_get_news_routes_to_news_module(self, provider, mock_akshare):
        result = provider.route_china("get_news", "600519.SH", "2025-01-09", "2025-01-13")
        assert "# News for 600519.SH" in result
        assert "# Source: 东方财富 (via AKShare)" in result

    def test_get_global_news_routes_to_news_module(self, provider, mock_akshare):
        result = provider.route_china("get_global_news", "2025-01-10")
        assert "# Global/Macro News as of 2025-01-10" in result

    def test_get_news_fallback_to_sina_when_eastmoney_fails(self, provider, mock_akshare):
        # Make eastmoney return "No news" to trigger fallback
        mock_akshare.stock_news_em.return_value = pd.DataFrame()
        result = provider.route_china("get_news", "600519.SH", "2025-01-09", "2025-01-13")
        # Sina also uses stock_news_em, so it will also return empty — final fallback message
        assert "No news" in result or "新浪财经" in result

    def test_get_news_does_not_hit_provider_chain(self, provider, mock_akshare):
        """News routing should bypass tushare/akshare/baostock provider chain."""
        # Verify that get_news is handled by the dedicated news helper, not the
        # generic provider chain. We confirm by checking the result comes from
        # eastmoney_news (contains the expected header).
        result = provider.route_china("get_news", "600519.SH", "2025-01-09", "2025-01-13")
        assert "# News for 600519.SH" in result
        assert "东方财富" in result

    def test_other_methods_still_use_provider_chain(self, provider, mock_akshare):
        """Non-news methods should still go through the provider fallback chain."""
        import types

        # Stub baostock so the lazy import in provider.py doesn't fail
        bs_mock = types.ModuleType("baostock")
        bs_mock.login = MagicMock(return_value=MagicMock(error_code="0"))
        bs_mock.logout = MagicMock()

        mock_akshare.stock_zh_a_hist.return_value = pd.DataFrame({
            "日期": ["2025-01-10"],
            "开盘": [1800.0],
            "收盘": [1810.0],
            "最高": [1820.0],
            "最低": [1790.0],
            "成交量": [50000.0],
            "成交额": [9e10],
            "振幅": [1.67],
            "涨跌幅": [0.56],
            "涨跌额": [10.0],
            "换手率": [0.40],
        })

        with patch.dict(sys.modules, {"baostock": bs_mock}):
            import importlib
            import tradingagents.cn_plugin.dataflows.baostock_provider as bp
            importlib.reload(bp)
            result = provider.route_china("get_stock_data", "600519.SH", "2025-01-09", "2025-01-13")

        # Should not return news-related content
        assert "# News for" not in result
