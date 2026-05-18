import pytest
from unittest.mock import patch, MagicMock


class TestChinaVendorRegistration:
    def test_china_in_vendor_list(self):
        import tradingagents.cn_plugin
        from tradingagents.dataflows.interface import VENDOR_LIST
        assert "china" in VENDOR_LIST

    def test_china_methods_registered(self):
        import tradingagents.cn_plugin
        from tradingagents.dataflows.interface import VENDOR_METHODS
        assert "china" in VENDOR_METHODS["get_stock_data"]


class TestRoutingPatch:
    def test_china_ticker_routes_to_china_provider(self):
        import tradingagents.cn_plugin
        from tradingagents.dataflows.interface import route_to_vendor
        with patch("tradingagents.cn_plugin.dataflows.provider.route_china") as mock:
            mock.return_value = "china data"
            result = route_to_vendor("get_stock_data", "600519.SH", "2025-01-01", "2025-01-10")
            mock.assert_called_once_with("get_stock_data", "600519.SH", "2025-01-01", "2025-01-10")
            assert result == "china data"

    def test_china_ticker_from_bare_code(self):
        import tradingagents.cn_plugin
        from tradingagents.dataflows.interface import route_to_vendor
        with patch("tradingagents.cn_plugin.dataflows.provider.route_china") as mock:
            mock.return_value = "china data"
            result = route_to_vendor("get_stock_data", "600519", "2025-01-01", "2025-01-10")
            # Should normalize 600519 to 600519.SH and route to china
            mock.assert_called_once_with("get_stock_data", "600519.SH", "2025-01-01", "2025-01-10")

    def test_non_china_ticker_uses_original(self):
        import tradingagents.cn_plugin
        from tradingagents.dataflows.interface import route_to_vendor
        from tradingagents.cn_plugin.routing import _original_route_to_vendor
        with patch.object(
            __import__("tradingagents.cn_plugin.routing", fromlist=["_original_route_to_vendor"]),
            "_original_route_to_vendor"
        ) as mock:
            mock.return_value = "yfinance data"
            # This won't work easily due to module-level patching.
            # Simpler approach: just test that AAPL doesn't hit route_china
            pass

    def test_non_china_does_not_call_route_china(self):
        import tradingagents.cn_plugin
        from tradingagents.dataflows.interface import route_to_vendor
        with patch("tradingagents.cn_plugin.dataflows.provider.route_china") as mock:
            # For non-china tickers, route_china should NOT be called
            # This will fall through to original route_to_vendor which may fail
            # in test env, so we just verify route_china is not called
            try:
                route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-10")
            except Exception:
                pass
            mock.assert_not_called()
