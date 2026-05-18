"""Batch analysis runner with concurrency control."""
import asyncio
import logging
from typing import List, Optional
from pathlib import Path

from tradingagents.cn_plugin.config import CN_CONFIG

logger = logging.getLogger(__name__)


def _analyze_single_sync(ticker: str, trade_date: str, config: dict) -> dict:
    """Run analysis for a single ticker synchronously.

    Returns dict with ticker, status, and result or error.
    """
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        graph = TradingAgentsGraph(config=config)
        result = graph.propagate(ticker, trade_date)
        return {"ticker": ticker, "status": "success", "result": result}
    except Exception as e:
        logger.error(f"Analysis failed for {ticker}: {e}")
        return {"ticker": ticker, "status": "error", "error": str(e)}


async def run_batch(
    tickers: List[str],
    trade_date: str,
    config: dict,
    max_concurrency: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> List[dict]:
    """Run batch analysis for multiple tickers with concurrency control.

    Args:
        tickers: List of ticker symbols
        trade_date: Analysis date (YYYY-MM-DD)
        config: TradingAgents config dict
        max_concurrency: Max parallel analyses (default from CN_CONFIG)
        output_dir: Directory for saving reports (optional)

    Returns:
        List of result dicts with ticker, status, and result/error.
    """
    concurrency = max_concurrency or CN_CONFIG.get("batch_max_concurrency", 2)
    semaphore = asyncio.Semaphore(concurrency)

    async def _limited(ticker: str) -> dict:
        async with semaphore:
            logger.info(f"Starting analysis for {ticker}")
            result = await asyncio.to_thread(
                _analyze_single_sync, ticker, trade_date, config
            )

            # Save report if output_dir specified and analysis succeeded
            if output_dir and result["status"] == "success" and result.get("result"):
                try:
                    from tradingagents.cn_plugin.reports.markdown_report import save_report
                    state = result["result"]
                    if isinstance(state, dict):
                        save_report(state, output_dir)
                        logger.info(f"Report saved for {ticker}")
                except Exception as e:
                    logger.warning(f"Failed to save report for {ticker}: {e}")

            return result

    tasks = [_limited(t) for t in tickers]
    results = await asyncio.gather(*tasks)
    return list(results)


def run_batch_sync(
    tickers: List[str],
    trade_date: str,
    config: dict,
    max_concurrency: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> List[dict]:
    """Synchronous wrapper for run_batch."""
    return asyncio.run(
        run_batch(tickers, trade_date, config, max_concurrency, output_dir)
    )


def generate_summary_report(results: List[dict]) -> str:
    """Generate a comparison summary from batch results.

    Args:
        results: List of result dicts from run_batch

    Returns:
        Markdown summary comparing all analyzed tickers.
    """
    lines = ["# 批量分析汇总报告", ""]

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]

    lines.append(f"**分析总数**: {len(results)} | **成功**: {len(success)} | **失败**: {len(failed)}")
    lines.append("")

    if success:
        lines.append("## 分析结果")
        lines.append("")
        lines.append("| 标的 | 最终决策 |")
        lines.append("|------|---------|")
        for r in success:
            ticker = r["ticker"]
            state = r.get("result", {})
            decision = "N/A"
            if isinstance(state, dict):
                decision = state.get("final_decision", "N/A")
                if len(decision) > 50:
                    decision = decision[:50] + "..."
            lines.append(f"| {ticker} | {decision} |")
        lines.append("")

    if failed:
        lines.append("## 失败记录")
        lines.append("")
        for r in failed:
            lines.append(f"- **{r['ticker']}**: {r.get('error', 'Unknown error')}")

    return "\n".join(lines)
