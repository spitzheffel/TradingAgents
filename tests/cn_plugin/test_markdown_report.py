import pytest
from pathlib import Path
import tempfile


@pytest.fixture
def sample_state():
    return {
        "company_of_interest": "600519.SH",
        "trade_date": "2025-05-16",
        "fundamentals_report": "贵州茅台基本面良好，市盈率25.3倍。",
        "market_report": "MACD金叉，RSI在60附近，趋势偏多。",
        "news_report": "近期无重大利空消息，白酒板块整体回暖。",
        "sentiment_report": "市场情绪偏乐观，北向资金持续流入。",
        "bull_report": "品牌护城河深厚，现金流充裕，估值合理。",
        "bear_report": "消费降级风险，高端白酒增速放缓。",
        "research_report": "综合来看多头逻辑更具说服力。",
        "trader_report": "建议逢低买入，目标价2100元。",
        "risk_report": "主要风险：政策监管、消费疲软。仓位建议不超过10%。",
        "final_decision": "**BUY** - 建议买入，中长期持有。",
    }


class TestGenerateReport:
    def test_contains_ticker_and_date(self, sample_state):
        from tradingagents.cn_plugin.reports.markdown_report import generate_report
        md = generate_report(sample_state)
        assert "600519.SH" in md
        assert "2025-05-16" in md

    def test_contains_all_sections(self, sample_state):
        from tradingagents.cn_plugin.reports.markdown_report import generate_report
        md = generate_report(sample_state)
        assert "## 基本面分析" in md
        assert "## 技术面分析" in md
        assert "## 新闻分析" in md
        assert "## 市场情绪" in md
        assert "## 多空辩论" in md
        assert "## 交易建议" in md
        assert "## 风险评估" in md
        assert "## 最终决策" in md

    def test_contains_agent_content(self, sample_state):
        from tradingagents.cn_plugin.reports.markdown_report import generate_report
        md = generate_report(sample_state)
        assert "贵州茅台基本面良好" in md
        assert "MACD金叉" in md
        assert "建议买入" in md

    def test_summary_extracts_signal(self, sample_state):
        from tradingagents.cn_plugin.reports.markdown_report import generate_report
        md = generate_report(sample_state)
        assert "BUY" in md

    def test_missing_fields_show_placeholder(self):
        from tradingagents.cn_plugin.reports.markdown_report import generate_report
        md = generate_report({"company_of_interest": "TEST", "trade_date": "2025-01-01"})
        assert "暂无数据" in md


class TestSaveReport:
    def test_saves_to_file(self, sample_state):
        from tradingagents.cn_plugin.reports.markdown_report import save_report
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report(sample_state, tmpdir)
            assert Path(path).exists()
            content = Path(path).read_text(encoding="utf-8")
            assert "600519.SH" in content
            assert "投资分析报告" in content
