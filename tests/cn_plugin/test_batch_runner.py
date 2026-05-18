import pytest
from unittest.mock import patch, MagicMock


class TestBatchRunner:
    @pytest.mark.asyncio
    async def test_runs_multiple_tickers(self):
        from tradingagents.cn_plugin.batch.runner import run_batch
        with patch("tradingagents.cn_plugin.batch.runner._analyze_single_sync") as mock:
            mock.return_value = {"ticker": "600519.SH", "status": "success", "result": {"final_decision": "BUY"}}
            results = await run_batch(
                tickers=["600519.SH", "000858.SZ"],
                trade_date="2025-05-16",
                config={},
            )
            assert len(results) == 2
            assert mock.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_failures_gracefully(self):
        from tradingagents.cn_plugin.batch.runner import run_batch
        def mock_analyze(ticker, date, config):
            if ticker == "BAD":
                return {"ticker": ticker, "status": "error", "error": "failed"}
            return {"ticker": ticker, "status": "success", "result": {}}

        with patch("tradingagents.cn_plugin.batch.runner._analyze_single_sync", side_effect=mock_analyze):
            results = await run_batch(
                tickers=["600519.SH", "BAD"],
                trade_date="2025-05-16",
                config={},
            )
            assert len(results) == 2
            success = [r for r in results if r["status"] == "success"]
            errors = [r for r in results if r["status"] == "error"]
            assert len(success) == 1
            assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(self):
        import asyncio
        from tradingagents.cn_plugin.batch.runner import run_batch

        concurrent_count = []
        current = 0

        def mock_analyze(ticker, date, config):
            nonlocal current
            import time
            # This runs in a thread, use threading lock
            current += 1
            concurrent_count.append(current)
            time.sleep(0.1)
            current -= 1
            return {"ticker": ticker, "status": "success", "result": {}}

        with patch("tradingagents.cn_plugin.batch.runner._analyze_single_sync", side_effect=mock_analyze):
            results = await run_batch(
                tickers=["A", "B", "C", "D"],
                trade_date="2025-05-16",
                config={},
                max_concurrency=2,
            )
            assert len(results) == 4
            assert max(concurrent_count) <= 2


class TestSummaryReport:
    def test_generates_summary(self):
        from tradingagents.cn_plugin.batch.runner import generate_summary_report
        results = [
            {"ticker": "600519.SH", "status": "success", "result": {"final_decision": "BUY"}},
            {"ticker": "000858.SZ", "status": "success", "result": {"final_decision": "HOLD"}},
            {"ticker": "BAD", "status": "error", "error": "timeout"},
        ]
        md = generate_summary_report(results)
        assert "批量分析汇总报告" in md
        assert "600519.SH" in md
        assert "BUY" in md
        assert "HOLD" in md
        assert "timeout" in md
        assert "成功**: 2" in md
        assert "失败**: 1" in md

    def test_all_failed(self):
        from tradingagents.cn_plugin.batch.runner import generate_summary_report
        results = [
            {"ticker": "BAD1", "status": "error", "error": "e1"},
            {"ticker": "BAD2", "status": "error", "error": "e2"},
        ]
        md = generate_summary_report(results)
        assert "失败**: 2" in md


class TestSyncWrapper:
    def test_sync_wrapper_works(self):
        from tradingagents.cn_plugin.batch.runner import run_batch_sync
        with patch("tradingagents.cn_plugin.batch.runner._analyze_single_sync") as mock:
            mock.return_value = {"ticker": "T", "status": "success", "result": {}}
            results = run_batch_sync(["T"], "2025-01-01", {})
            assert len(results) == 1
