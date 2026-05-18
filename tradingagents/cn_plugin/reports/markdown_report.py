"""Full Markdown report generator — assembles all agent outputs into one document."""
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_report(state: dict) -> str:
    """Generate a full investment analysis report in Markdown format.

    Args:
        state: The graph state dict containing all agent reports.

    Returns:
        Complete Markdown-formatted report string.
    """
    ticker = state.get("company_of_interest", "Unknown")
    date = state.get("trade_date", "Unknown")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = [
        f"# {ticker} 投资分析报告",
        f"> 分析日期：{date} | 生成时间：{now}\n",
        "---\n",
        "## 摘要\n",
        _build_summary(state),
        "\n---\n",
        "## 基本面分析\n",
        state.get("fundamentals_report", "_暂无数据_"),
        "\n---\n",
        "## 技术面分析\n",
        state.get("market_report", "_暂无数据_"),
        "\n---\n",
        "## 新闻分析\n",
        state.get("news_report", "_暂无数据_"),
        "\n---\n",
        "## 市场情绪\n",
        state.get("sentiment_report", "_暂无数据_"),
        "\n---\n",
        "## 多空辩论\n",
        "### 看多观点\n",
        state.get("bull_report", "_暂无数据_"),
        "\n### 看空观点\n",
        state.get("bear_report", "_暂无数据_"),
        "\n### 研究总监总结\n",
        state.get("research_report", "_暂无数据_"),
        "\n---\n",
        "## 交易建议\n",
        state.get("trader_report", "_暂无数据_"),
        "\n---\n",
        "## 风险评估\n",
        state.get("risk_report", "_暂无数据_"),
        "\n---\n",
        "## 最终决策\n",
        state.get("final_decision", "_暂无数据_"),
    ]

    return "\n".join(sections)


def _build_summary(state: dict) -> str:
    """Build executive summary from final decision and key points."""
    decision = state.get("final_decision", "")
    ticker = state.get("company_of_interest", "")
    date = state.get("trade_date", "")

    if not decision:
        return f"对 {ticker} 在 {date} 的综合分析报告。"

    # Extract BUY/HOLD/SELL signal if present
    signal = "未明确"
    for s in ["BUY", "HOLD", "SELL", "买入", "持有", "卖出"]:
        if s in decision.upper():
            signal = s
            break

    return f"**标的**：{ticker}  \n**日期**：{date}  \n**信号**：{signal}\n"


def save_report(state: dict, output_dir: str) -> str:
    """Generate and save the report to a file.

    Args:
        state: Graph state dict
        output_dir: Directory to save the report

    Returns:
        Path to the saved report file.
    """
    ticker = state.get("company_of_interest", "unknown")
    date = state.get("trade_date", "unknown")

    report_content = generate_report(state)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"{ticker}_{date}_full_report.md"
    filepath = output_path / filename
    filepath.write_text(report_content, encoding="utf-8")

    return str(filepath)
