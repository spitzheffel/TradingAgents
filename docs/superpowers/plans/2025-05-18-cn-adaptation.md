# CN Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add A-share market support, Chinese prompts, PG cache, report export, and batch analysis to TradingAgents via a zero-upstream-modification plugin architecture.

**Architecture:** All features live under `tradingagents/cn_plugin/` and activate via `import tradingagents.cn_plugin`. The plugin dynamically registers a china vendor, wraps `route_to_vendor` for ticker normalization + caching, and wraps `get_language_instruction` for Chinese prompt enhancement. Zero upstream files are modified.

**Tech Stack:** Python 3.10+, Tushare, AKShare, BaoStock, psycopg3 (PostgreSQL), stockstats, asyncio

---

## File Structure

```
tradingagents/cn_plugin/
├── __init__.py              # Plugin activation: registers vendor, patches routing + prompts
├── config.py                # CN-specific config defaults, merged via set_config()
├── ticker.py                # Ticker normalization + market detection
├── routing.py               # Wraps route_to_vendor: ticker norm + cache + china routing
├── dataflows/
│   ├── __init__.py
│   ├── provider.py          # Fallback chain orchestrator
│   ├── tushare_provider.py  # Tushare API implementations
│   ├── akshare_provider.py  # AKShare API implementations
│   ├── baostock_provider.py # BaoStock API implementations
│   ├── eastmoney_news.py    # 东方财富 news via AKShare
│   ├── sina_news.py         # 新浪财经 news
│   └── sentiment.py         # Chinese sentiment aggregation
├── cache/
│   ├── __init__.py
│   ├── pg_client.py         # Connection pool management
│   ├── cache_manager.py     # Read/write logic with TTL
│   └── schema.sql           # DDL for TimescaleDB tables
├── prompts/
│   ├── __init__.py
│   └── zh_cn.py             # Chinese prompt enhancement text
├── reports/
│   ├── __init__.py
│   └── markdown_report.py   # Full report assembly
└── batch/
    ├── __init__.py
    └── runner.py             # Concurrent batch analysis
```

**Tests:**
```
tests/cn_plugin/
├── __init__.py
├── test_ticker.py
├── test_routing.py
├── test_config.py
├── test_tushare_provider.py
├── test_akshare_provider.py
├── test_baostock_provider.py
├── test_cache_manager.py
├── test_prompts.py
├── test_markdown_report.py
└── test_batch_runner.py
```

---

## Task 1: Plugin skeleton + Ticker normalization

**Files:**
- Create: `tradingagents/cn_plugin/__init__.py`
- Create: `tradingagents/cn_plugin/ticker.py`
- Create: `tradingagents/cn_plugin/config.py`
- Create: `tests/cn_plugin/__init__.py`
- Create: `tests/cn_plugin/test_ticker.py`

- [ ] **Step 1: Write failing tests for ticker normalization**

```python
# tests/cn_plugin/test_ticker.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cn_plugin/test_ticker.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement ticker module**

```python
# tradingagents/cn_plugin/ticker.py
"""Ticker normalization and China market detection."""
import re

_CHINA_SUFFIXES = {".SH", ".SZ", ".BJ"}

_PREFIX_MAP = {
    "SH": ".SH",
    "SZ": ".SZ",
    "BJ": ".BJ",
}

_CODE_RULES = [
    (re.compile(r"^6\d{5}$"), ".SH"),   # 上海主板 + 科创板
    (re.compile(r"^00[0-3]\d{3}$"), ".SZ"),  # 深圳主板/中小板
    (re.compile(r"^30[01]\d{3}$"), ".SZ"),   # 创业板
    (re.compile(r"^688\d{3}$"), ".SH"),      # 科创板
    (re.compile(r"^[48]\d{5}$"), ".BJ"),     # 北交所
]


def normalize_ticker(symbol: str) -> str:
    """Normalize any China ticker input format to CODE.EXCHANGE.

    Supports: 600519, 600519.SH, SH600519, sh600519.
    Non-China tickers are returned unchanged.
    """
    s = symbol.strip()

    # Already has China suffix
    upper = s.upper()
    for suffix in _CHINA_SUFFIXES:
        if upper.endswith(suffix):
            code = upper[: -len(suffix)]
            if code.endswith("."):
                code = code[:-1]
            return f"{code}{suffix}"

    # Has exchange prefix (SH600519, sz000858, BJ830799)
    for prefix, suffix in _PREFIX_MAP.items():
        if upper.startswith(prefix) and upper[len(prefix):].isdigit():
            code = upper[len(prefix):]
            return f"{code}{suffix}"

    # Pure 6-digit number — infer exchange
    if s.isdigit() and len(s) == 6:
        for pattern, suffix in _CODE_RULES:
            if pattern.match(s):
                return f"{s}{suffix}"

    # Not a China ticker — return as-is
    return symbol


def is_china_ticker(symbol: str) -> bool:
    """Check if a normalized ticker belongs to a Chinese exchange."""
    upper = symbol.upper()
    return any(upper.endswith(suffix) for suffix in _CHINA_SUFFIXES)
```

- [ ] **Step 4: Create config module**

```python
# tradingagents/cn_plugin/config.py
"""CN plugin configuration defaults."""
import os

CN_CONFIG = {
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
    "china_data_priority": ["tushare", "akshare", "baostock"],
    "cache_enabled": bool(os.getenv("TRADINGAGENTS_PG_DSN", "")),
    "cache_backend": "postgresql",
    "pg_dsn": os.getenv("TRADINGAGENTS_PG_DSN", ""),
    "cache_ttl_intraday_minutes": 15,
    "output_language": "Chinese",
    "global_news_queries": [
        "央行 LPR 利率 货币政策",
        "A股 沪深 GDP 经济数据",
        "地缘政治 贸易摩擦 制裁",
        "美联储 欧央行 日央行 政策",
        "原油 大宗商品 供应链 能源",
    ],
    "batch_max_concurrency": 2,
}
```

- [ ] **Step 5: Create plugin init (skeleton)**

```python
# tradingagents/cn_plugin/__init__.py
"""CN Plugin — activates China market support on import.

Usage:
    import tradingagents.cn_plugin
"""
from tradingagents.dataflows.config import set_config
from tradingagents.cn_plugin.config import CN_CONFIG

# Merge CN config (does not overwrite user-set values)
_merged = {k: v for k, v in CN_CONFIG.items() if v}
set_config(_merged)
```

- [ ] **Step 6: Create test __init__**

```python
# tests/cn_plugin/__init__.py
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/cn_plugin/test_ticker.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add tradingagents/cn_plugin/ tests/cn_plugin/
git commit -m "feat(cn): add plugin skeleton with ticker normalization"
```

---

## Task 2: Routing wrapper (vendor registration + ticker interception)

**Files:**
- Create: `tradingagents/cn_plugin/routing.py`
- Modify: `tradingagents/cn_plugin/__init__.py`
- Create: `tests/cn_plugin/test_routing.py`

- [ ] **Step 1: Write failing tests for routing**

```python
# tests/cn_plugin/test_routing.py
import pytest
from unittest.mock import patch, MagicMock


class TestChinaVendorRegistration:
    def test_china_in_vendor_list(self):
        import tradingagents.cn_plugin  # noqa: F401
        from tradingagents.dataflows.interface import VENDOR_LIST
        assert "china" in VENDOR_LIST

    def test_china_methods_registered(self):
        import tradingagents.cn_plugin  # noqa: F401
        from tradingagents.dataflows.interface import VENDOR_METHODS
        assert "china" in VENDOR_METHODS["get_stock_data"]


class TestRoutingPatch:
    def test_china_ticker_routes_to_china_vendor(self):
        import tradingagents.cn_plugin  # noqa: F401
        from tradingagents.dataflows.interface import route_to_vendor
        with patch("tradingagents.cn_plugin.dataflows.provider.get_stock_data_china") as mock:
            mock.return_value = "mocked data"
            result = route_to_vendor("get_stock_data", "600519.SH", "2025-01-01", "2025-01-10")
            mock.assert_called_once()

    def test_non_china_ticker_unchanged(self):
        import tradingagents.cn_plugin  # noqa: F401
        from tradingagents.dataflows.interface import route_to_vendor
        with patch("tradingagents.dataflows.y_finance.get_YFin_data_online") as mock:
            mock.return_value = "yfinance data"
            result = route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-10")
            mock.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cn_plugin/test_routing.py -v`
Expected: FAIL

- [ ] **Step 3: Implement routing wrapper**

```python
# tradingagents/cn_plugin/routing.py
"""Route enhancement: ticker normalization + China market interception."""
import tradingagents.dataflows.interface as _iface
from tradingagents.cn_plugin.ticker import normalize_ticker, is_china_ticker

_original_route_to_vendor = _iface.route_to_vendor

# Methods where the first positional arg is a ticker/symbol
_TICKER_FIRST_METHODS = {
    "get_stock_data", "get_indicators", "get_fundamentals",
    "get_balance_sheet", "get_cashflow", "get_income_statement",
    "get_news", "get_insider_transactions",
}


def _enhanced_route_to_vendor(method: str, *args, **kwargs):
    """Wrap route_to_vendor: normalize ticker, force china vendor for A-share."""
    # Normalize ticker if this method takes one as first arg
    if method in _TICKER_FIRST_METHODS and args:
        normalized = normalize_ticker(args[0])
        args = (normalized,) + args[1:]

        # Force china vendor for A-share tickers
        if is_china_ticker(normalized):
            from tradingagents.cn_plugin.dataflows.provider import route_china
            return route_china(method, *args, **kwargs)

    return _original_route_to_vendor(method, *args, **kwargs)


def patch_routing():
    """Monkey-patch route_to_vendor in the interface module."""
    _iface.route_to_vendor = _enhanced_route_to_vendor


def unpatch_routing():
    """Restore original route_to_vendor (for testing)."""
    _iface.route_to_vendor = _original_route_to_vendor
```

- [ ] **Step 4: Create provider stub**

```python
# tradingagents/cn_plugin/dataflows/__init__.py
```

```python
# tradingagents/cn_plugin/dataflows/provider.py
"""China data provider — fallback chain orchestrator."""
from tradingagents.cn_plugin.config import CN_CONFIG


def route_china(method: str, *args, **kwargs) -> str:
    """Route to China-specific provider with fallback chain."""
    from tradingagents.cn_plugin.dataflows import tushare_provider, akshare_provider, baostock_provider

    _PROVIDER_MAP = {
        "tushare": tushare_provider,
        "akshare": akshare_provider,
        "baostock": baostock_provider,
    }

    priority = CN_CONFIG.get("china_data_priority", ["tushare", "akshare", "baostock"])

    for provider_name in priority:
        provider = _PROVIDER_MAP.get(provider_name)
        if provider is None:
            continue
        func = getattr(provider, method, None)
        if func is None:
            continue
        try:
            result = func(*args, **kwargs)
            if result and "No data" not in str(result):
                return result
        except Exception:
            continue

    symbol = args[0] if args else "unknown"
    return f"No data available for {symbol} from any China data source"
```

- [ ] **Step 5: Register vendor and patch in plugin init**

```python
# tradingagents/cn_plugin/__init__.py
"""CN Plugin — activates China market support on import.

Usage:
    import tradingagents.cn_plugin
"""
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS
from tradingagents.cn_plugin.config import CN_CONFIG
from tradingagents.cn_plugin.routing import patch_routing

# 1. Merge CN config
_merged = {k: v for k, v in CN_CONFIG.items() if v}
set_config(_merged)

# 2. Register china vendor
if "china" not in VENDOR_LIST:
    VENDOR_LIST.append("china")

# Register placeholder implementations in VENDOR_METHODS
from tradingagents.cn_plugin.dataflows.provider import route_china as _route

def _make_china_impl(method_name):
    def _impl(*args, **kwargs):
        return route_china(method_name, *args, **kwargs)
    return _impl

for method_name in VENDOR_METHODS:
    if "china" not in VENDOR_METHODS[method_name]:
        VENDOR_METHODS[method_name]["china"] = _make_china_impl(method_name)

# 3. Patch routing for ticker normalization + china interception
patch_routing()
```

- [ ] **Step 6: Create stub provider files (will be implemented in Task 3-5)**

```python
# tradingagents/cn_plugin/dataflows/tushare_provider.py
"""Tushare data provider — stub, implemented in Task 3."""

def get_stock_data(symbol, start_date, end_date):
    raise NotImplementedError("Tushare provider not yet implemented")
```

```python
# tradingagents/cn_plugin/dataflows/akshare_provider.py
"""AKShare data provider — stub, implemented in Task 4."""

def get_stock_data(symbol, start_date, end_date):
    raise NotImplementedError("AKShare provider not yet implemented")
```

```python
# tradingagents/cn_plugin/dataflows/baostock_provider.py
"""BaoStock data provider — stub, implemented in Task 5."""

def get_stock_data(symbol, start_date, end_date):
    raise NotImplementedError("BaoStock provider not yet implemented")
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/cn_plugin/ -v`
Expected: test_ticker passes; test_routing may need mock adjustments for stubs

- [ ] **Step 8: Commit**

```bash
git add tradingagents/cn_plugin/ tests/cn_plugin/
git commit -m "feat(cn): add routing wrapper with ticker interception"
```

---

## Task 3: Tushare provider implementation

**Files:**
- Create: `tradingagents/cn_plugin/dataflows/tushare_provider.py`
- Create: `tests/cn_plugin/test_tushare_provider.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/cn_plugin/test_tushare_provider.py
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


@pytest.fixture
def mock_tushare():
    with patch("tradingagents.cn_plugin.dataflows.tushare_provider._get_pro") as mock:
        pro = MagicMock()
        mock.return_value = pro
        yield pro


class TestTushareGetStockData:
    def test_returns_csv_string(self, mock_tushare):
        from tradingagents.cn_plugin.dataflows.tushare_provider import get_stock_data
        mock_tushare.daily.return_value = pd.DataFrame({
            "trade_date": ["20250501", "20250502"],
            "open": [1800.0, 1810.0],
            "high": [1820.0, 1830.0],
            "low": [1790.0, 1800.0],
            "close": [1810.0, 1825.0],
            "vol": [50000, 48000],
        })
        result = get_stock_data("600519.SH", "2025-05-01", "2025-05-10")
        assert "600519" in result
        assert "1810" in result
        assert "Date" in result or "trade_date" in result

    def test_no_token_raises(self):
        from tradingagents.cn_plugin.dataflows.tushare_provider import get_stock_data
        with patch("tradingagents.cn_plugin.dataflows.tushare_provider._get_pro", side_effect=ValueError("No token")):
            with pytest.raises(ValueError):
                get_stock_data("600519.SH", "2025-05-01", "2025-05-10")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cn_plugin/test_tushare_provider.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Tushare provider**

```python
# tradingagents/cn_plugin/dataflows/tushare_provider.py
"""Tushare data provider for A-share market."""
from datetime import datetime
import pandas as pd
from tradingagents.cn_plugin.config import CN_CONFIG
from tradingagents.dataflows.stockstats_utils import StockstatsUtils

_pro_api = None


def _get_pro():
    global _pro_api
    if _pro_api is None:
        import tushare as ts
        token = CN_CONFIG.get("tushare_token", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN not configured")
        ts.set_token(token)
        _pro_api = ts.pro_api()
    return _pro_api


def _date_to_ts(date_str: str) -> str:
    """Convert yyyy-mm-dd to yyyymmdd."""
    return date_str.replace("-", "")


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    pro = _get_pro()
    ts_code = symbol.upper()
    df = pro.daily(
        ts_code=ts_code,
        start_date=_date_to_ts(start_date),
        end_date=_date_to_ts(end_date),
    )
    if df is None or df.empty:
        return f"No data found for {symbol} between {start_date} and {end_date}"

    df = df.sort_values("trade_date")
    df["Date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "vol": "Volume",
    })
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    csv_string = df.to_csv(index=False)

    header = f"# Stock data for {symbol} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Source: Tushare\n\n"
    return header + csv_string


def get_indicators(symbol: str, start_date: str, end_date: str) -> str:
    """Technical indicators via stockstats (reuses upstream utility)."""
    indicators = ["macd", "macds", "macdh", "rsi_14", "close_50_sma", "close_10_ema", "boll", "boll_ub", "boll_lb"]
    results = []
    for ind in indicators:
        val = StockstatsUtils.get_stock_stats(symbol, ind, end_date)
        results.append(f"{ind}: {val}")
    return "\n".join(results)


def get_fundamentals(symbol: str) -> str:
    pro = _get_pro()
    ts_code = symbol.upper()
    basic = pro.daily_basic(ts_code=ts_code, fields="ts_code,trade_date,pe,pb,total_mv,circ_mv")
    info = pro.stock_basic(ts_code=ts_code, fields="ts_code,name,industry,area,market,list_date")

    parts = [f"# Fundamentals for {symbol}\n"]
    if info is not None and not info.empty:
        row = info.iloc[0]
        parts.append(f"Name: {row.get('name', 'N/A')}")
        parts.append(f"Industry: {row.get('industry', 'N/A')}")
        parts.append(f"Market: {row.get('market', 'N/A')}")
        parts.append(f"Listed: {row.get('list_date', 'N/A')}")
    if basic is not None and not basic.empty:
        latest = basic.sort_values("trade_date", ascending=False).iloc[0]
        parts.append(f"\nLatest metrics ({latest.get('trade_date', '')}):")
        parts.append(f"PE: {latest.get('pe', 'N/A')}")
        parts.append(f"PB: {latest.get('pb', 'N/A')}")
        parts.append(f"Total Market Cap: {latest.get('total_mv', 'N/A')} 万元")
        parts.append(f"Circulating Market Cap: {latest.get('circ_mv', 'N/A')} 万元")
    return "\n".join(parts)


def get_balance_sheet(symbol: str) -> str:
    pro = _get_pro()
    df = pro.balancesheet(ts_code=symbol.upper(), fields="ts_code,ann_date,end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int")
    if df is None or df.empty:
        return f"No balance sheet data for {symbol}"
    df = df.head(4)
    header = f"# Balance Sheet for {symbol} (recent 4 periods)\n# Source: Tushare\n\n"
    return header + df.to_csv(index=False)


def get_cashflow(symbol: str) -> str:
    pro = _get_pro()
    df = pro.cashflow(ts_code=symbol.upper(), fields="ts_code,ann_date,end_date,n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act")
    if df is None or df.empty:
        return f"No cashflow data for {symbol}"
    df = df.head(4)
    header = f"# Cash Flow for {symbol} (recent 4 periods)\n# Source: Tushare\n\n"
    return header + df.to_csv(index=False)


def get_income_statement(symbol: str) -> str:
    pro = _get_pro()
    df = pro.income(ts_code=symbol.upper(), fields="ts_code,ann_date,end_date,revenue,n_income,basic_eps")
    if df is None or df.empty:
        return f"No income statement data for {symbol}"
    df = df.head(4)
    header = f"# Income Statement for {symbol} (recent 4 periods)\n# Source: Tushare\n\n"
    return header + df.to_csv(index=False)


def get_insider_transactions(symbol: str) -> str:
    pro = _get_pro()
    df = pro.stk_holdertrade(ts_code=symbol.upper())
    if df is None or df.empty:
        return f"No insider transaction data for {symbol}"
    df = df.head(20)
    header = f"# Insider Transactions for {symbol}\n# Source: Tushare\n\n"
    return header + df.to_csv(index=False)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/cn_plugin/test_tushare_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/cn_plugin/dataflows/tushare_provider.py tests/cn_plugin/test_tushare_provider.py
git commit -m "feat(cn): implement Tushare data provider"
```

---

## Task 4: AKShare provider implementation

**Files:**
- Create: `tradingagents/cn_plugin/dataflows/akshare_provider.py`
- Create: `tests/cn_plugin/test_akshare_provider.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/cn_plugin/test_akshare_provider.py
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


@pytest.fixture
def mock_ak():
    with patch("tradingagents.cn_plugin.dataflows.akshare_provider.ak") as mock:
        yield mock


class TestAkshareGetStockData:
    def test_returns_csv_string(self, mock_ak):
        from tradingagents.cn_plugin.dataflows.akshare_provider import get_stock_data
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame({
            "日期": ["2025-05-01", "2025-05-02"],
            "开盘": [1800.0, 1810.0],
            "最高": [1820.0, 1830.0],
            "最低": [1790.0, 1800.0],
            "收盘": [1810.0, 1825.0],
            "成交量": [50000, 48000],
        })
        result = get_stock_data("600519.SH", "2025-05-01", "2025-05-10")
        assert "600519" in result
        assert "1810" in result

    def test_empty_data(self, mock_ak):
        from tradingagents.cn_plugin.dataflows.akshare_provider import get_stock_data
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        result = get_stock_data("600519.SH", "2025-05-01", "2025-05-10")
        assert "No data" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cn_plugin/test_akshare_provider.py -v`
Expected: FAIL

- [ ] **Step 3: Implement AKShare provider**

See spec for full implementation. Key mappings:
- `ak.stock_zh_a_hist(symbol=code, period="daily", start_date, end_date)` → OHLCV
- `ak.stock_individual_info_em(symbol=code)` → fundamentals
- `ak.stock_balance_sheet_by_report_em(symbol=code)` → balance sheet
- `ak.stock_cash_flow_sheet_by_report_em(symbol=code)` → cashflow
- `ak.stock_profit_sheet_by_report_em(symbol=code)` → income statement
- `ak.stock_hold_management_detail_em(symbol=code)` → insider transactions

Column rename: 日期→Date, 开盘→Open, 最高→High, 最低→Low, 收盘→Close, 成交量→Volume

- [ ] **Step 4: Run tests**

Run: `pytest tests/cn_plugin/test_akshare_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/cn_plugin/dataflows/akshare_provider.py tests/cn_plugin/test_akshare_provider.py
git commit -m "feat(cn): implement AKShare data provider"
```

---

## Task 5: BaoStock provider implementation

**Files:**
- Create: `tradingagents/cn_plugin/dataflows/baostock_provider.py`
- Create: `tests/cn_plugin/test_baostock_provider.py`

- [ ] **Step 1: Write failing tests**

Similar structure to Task 4. BaoStock uses `bs.query_history_k_data_plus()` for OHLCV.
Key difference: BaoStock requires `bs.login()` / `bs.logout()` session management.
Ticker format: `sh.600519` (lowercase prefix + dot + code).

- [ ] **Step 2: Implement BaoStock provider**

Key mappings:
- `bs.query_history_k_data_plus(code="sh.600519", ...)` → OHLCV
- `bs.query_profit_data(code="sh.600519", ...)` → fundamentals (limited)
- `bs.query_balance_data(code="sh.600519", ...)` → balance sheet
- `bs.query_cash_flow_data(code="sh.600519", ...)` → cashflow

Note: BaoStock doesn't cover all endpoints (no insider transactions, limited news). Those methods should return a "not available from BaoStock" message.

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cn): implement BaoStock data provider"
```

---

## Task 6: Chinese news and sentiment sources

**Files:**
- Create: `tradingagents/cn_plugin/dataflows/eastmoney_news.py`
- Create: `tradingagents/cn_plugin/dataflows/sina_news.py`
- Create: `tradingagents/cn_plugin/dataflows/sentiment.py`

- [ ] **Step 1: Write failing tests for eastmoney_news**

Test that `get_news("600519.SH", start, end)` returns formatted news string.
Test that `get_global_news(date, days, limit)` returns macro news.
Mock `ak.stock_news_em` and `ak.news_cctv`.

- [ ] **Step 2: Implement eastmoney_news.py**

```python
# Key functions:
def get_news(ticker: str, start_date: str, end_date: str) -> str:
    code = ticker.split(".")[0]
    df = ak.stock_news_em(symbol=code)
    # Filter by date range, format as structured text
    ...

def get_global_news(curr_date: str, look_back_days=None, limit=None) -> str:
    df = ak.news_cctv(date=curr_date)
    # Also fetch ak.news_economic_baidu()
    # Combine, deduplicate, format
    ...
```

- [ ] **Step 3: Implement sina_news.py**

Scrape sina finance news for individual stocks. Format and merge with eastmoney results.

- [ ] **Step 4: Implement sentiment.py**

```python
def get_china_sentiment(ticker: str) -> str:
    code = ticker.split(".")[0]
    comment = ak.stock_comment_em(symbol=code)  # 千股千评
    # Format sentiment summary
    ...
```

- [ ] **Step 5: Register news functions in provider.py fallback chain**

Update `provider.py` to route `get_news` and `get_global_news` to china news sources.

- [ ] **Step 6: Run tests, commit**

```bash
git commit -m "feat(cn): add Chinese news and sentiment data sources"
```

---

## Task 7: Agent Prompt Chinese enhancement

**Files:**
- Create: `tradingagents/cn_plugin/prompts/__init__.py`
- Create: `tradingagents/cn_plugin/prompts/zh_cn.py`
- Modify: `tradingagents/cn_plugin/__init__.py` (add prompt patching)
- Create: `tests/cn_plugin/test_prompts.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cn_plugin/test_prompts.py
def test_zh_instruction_contains_terminology():
    import tradingagents.cn_plugin
    from tradingagents.agents.utils.agent_utils import get_language_instruction
    instruction = get_language_instruction()
    assert "市盈率" in instruction
    assert "简体中文" in instruction
```

- [ ] **Step 2: Implement zh_cn.py**

```python
# tradingagents/cn_plugin/prompts/zh_cn.py
ZH_INSTRUCTION = """
请使用简体中文撰写完整报告。遵循以下规范：

**术语对照**：
- PE Ratio → 市盈率，PB Ratio → 市净率
- Market Cap → 总市值，EPS → 每股收益
- Revenue → 营业收入，Net Income → 净利润
- ROE → 净资产收益率，Debt-to-Equity → 资产负债率
- MACD → MACD 指标，RSI → 相对强弱指标
- Bullish → 看多/多头，Bearish → 看空/空头
- Support → 支撑位，Resistance → 压力位

**格式要求**：
- 报告标题使用中文
- 数据表格保留数字精度
- 货币单位使用人民币（元/万元/亿元），如涉及美股则用美元
- 日期使用 YYYY-MM-DD 格式
- 百分比保留两位小数
- Markdown 表格必须包含
"""
```

- [ ] **Step 3: Patch get_language_instruction in plugin init**

```python
# In cn_plugin/__init__.py, add:
from tradingagents.cn_plugin.prompts.zh_cn import ZH_INSTRUCTION
import tradingagents.agents.utils.agent_utils as _agent_utils

_original_get_language_instruction = _agent_utils.get_language_instruction

def _zh_language_instruction() -> str:
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() in ("chinese", "中文"):
        return ZH_INSTRUCTION
    return _original_get_language_instruction()

_agent_utils.get_language_instruction = _zh_language_instruction
```

- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(cn): add Chinese prompt enhancement with terminology"
```

---

## Task 8: PostgreSQL cache layer

**Files:**
- Create: `tradingagents/cn_plugin/cache/__init__.py`
- Create: `tradingagents/cn_plugin/cache/pg_client.py`
- Create: `tradingagents/cn_plugin/cache/cache_manager.py`
- Create: `tradingagents/cn_plugin/cache/schema.sql`
- Create: `tests/cn_plugin/test_cache_manager.py`
- Modify: `tradingagents/cn_plugin/routing.py` (integrate cache)

- [ ] **Step 1: Write schema.sql**

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ticker TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC,
    volume BIGINT,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, trade_date)
);
SELECT create_hypertable('ohlcv_daily', 'trade_date', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS data_cache (
    cache_key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    report_content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 2: Implement pg_client.py**

```python
# Connection pool using psycopg3
import psycopg_pool
from tradingagents.cn_plugin.config import CN_CONFIG

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        dsn = CN_CONFIG.get("pg_dsn", "")
        if not dsn:
            return None
        _pool = psycopg_pool.ConnectionPool(dsn, min_size=1, max_size=5)
    return _pool
```

- [ ] **Step 3: Implement cache_manager.py**

```python
def cache_get(key: str) -> str | None:
    """Read from cache. Returns None on miss or if PG unavailable."""

def cache_set(key: str, value: str) -> None:
    """Write to cache. Silent no-op if PG unavailable."""

def make_cache_key(method: str, *args) -> str:
    """Deterministic cache key from method + args."""
```

- [ ] **Step 4: Integrate cache into routing.py**

Add cache lookup before provider call, cache write after successful fetch.
Only cache when `cache_enabled` is True and `pg_dsn` is non-empty.

- [ ] **Step 5: Write tests (mock PG), run, commit**

```bash
git commit -m "feat(cn): add PostgreSQL cache layer with TimescaleDB"
```

---

## Task 9: Markdown report export

**Files:**
- Create: `tradingagents/cn_plugin/reports/__init__.py`
- Create: `tradingagents/cn_plugin/reports/markdown_report.py`
- Create: `tests/cn_plugin/test_markdown_report.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cn_plugin/test_markdown_report.py
def test_generates_full_report():
    from tradingagents.cn_plugin.reports.markdown_report import generate_report
    state = {
        "company_of_interest": "600519.SH",
        "trade_date": "2025-05-16",
        "fundamentals_report": "基本面内容",
        "market_report": "技术面内容",
        "news_report": "新闻内容",
        "sentiment_report": "情绪内容",
        "bull_report": "看多观点",
        "bear_report": "看空观点",
        "research_report": "研究总结",
        "trader_report": "交易建议",
        "risk_report": "风控意见",
        "final_decision": "BUY",
    }
    md = generate_report(state)
    assert "# 600519.SH 投资分析报告" in md
    assert "基本面内容" in md
    assert "交易建议" in md
```

- [ ] **Step 2: Implement markdown_report.py**

```python
from datetime import datetime

def generate_report(state: dict) -> str:
    ticker = state.get("company_of_interest", "Unknown")
    date = state.get("trade_date", "Unknown")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = [
        f"# {ticker} 投资分析报告",
        f"> 分析日期：{date} | 生成时间：{now}\n",
        "## 基本面分析", state.get("fundamentals_report", "无数据"),
        "## 技术面分析", state.get("market_report", "无数据"),
        "## 新闻分析", state.get("news_report", "无数据"),
        "## 市场情绪", state.get("sentiment_report", "无数据"),
        "## 多空辩论",
        "### 看多观点", state.get("bull_report", "无数据"),
        "### 看空观点", state.get("bear_report", "无数据"),
        "### 研究总监总结", state.get("research_report", "无数据"),
        "## 交易建议", state.get("trader_report", "无数据"),
        "## 风险评估", state.get("risk_report", "无数据"),
        "## 最终决策", state.get("final_decision", "无数据"),
    ]
    return "\n\n".join(sections)
```

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cn): add Markdown report export"
```

---

## Task 10: Batch analysis runner

**Files:**
- Create: `tradingagents/cn_plugin/batch/__init__.py`
- Create: `tradingagents/cn_plugin/batch/runner.py`
- Create: `tests/cn_plugin/test_batch_runner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cn_plugin/test_batch_runner.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_batch_runs_multiple_tickers():
    from tradingagents.cn_plugin.batch.runner import run_batch
    with patch("tradingagents.cn_plugin.batch.runner._analyze_single") as mock:
        mock.return_value = {"ticker": "600519.SH", "decision": "BUY"}
        results = await run_batch(
            tickers=["600519.SH", "000858.SZ"],
            trade_date="2025-05-16",
            config={},
        )
        assert len(results) == 2
        assert mock.call_count == 2
```

- [ ] **Step 2: Implement runner.py**

```python
import asyncio
from typing import List
from tradingagents.cn_plugin.config import CN_CONFIG

async def _analyze_single(ticker: str, trade_date: str, config: dict) -> dict:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph = TradingAgentsGraph(config=config)
    result = graph.propagate(ticker, trade_date)
    return {"ticker": ticker, "result": result}

async def run_batch(
    tickers: List[str],
    trade_date: str,
    config: dict,
    max_concurrency: int = None,
) -> List[dict]:
    concurrency = max_concurrency or CN_CONFIG.get("batch_max_concurrency", 2)
    semaphore = asyncio.Semaphore(concurrency)
    
    async def _limited(ticker):
        async with semaphore:
            try:
                return await asyncio.to_thread(
                    _analyze_single_sync, ticker, trade_date, config
                )
            except Exception as e:
                return {"ticker": ticker, "error": str(e)}

    tasks = [_limited(t) for t in tickers]
    return await asyncio.gather(*tasks)

def _analyze_single_sync(ticker, trade_date, config):
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph = TradingAgentsGraph(config=config)
    result = graph.propagate(ticker, trade_date)
    return {"ticker": ticker, "result": result}
```

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cn): add batch analysis runner with concurrency control"
```

---

## Task 11: Dependencies and final integration

**Files:**
- Modify: `pyproject.toml` (add optional deps)
- Create: `tradingagents/cn_plugin/README.md` (usage docs)

- [ ] **Step 1: Add optional dependency group to pyproject.toml**

Add under `[project.optional-dependencies]`:
```toml
cn = [
    "tushare>=1.4.2",
    "akshare>=1.14.0",
    "baostock>=0.8.8",
    "psycopg[binary]>=3.2.0",
    "psycopg-pool>=3.2.0",
]
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(cn): add optional dependency group and integration docs"
```

---

## Summary

| Task | Description | Depends On |
|------|------------|-----------|
| 1 | Plugin skeleton + Ticker normalization | — |
| 2 | Routing wrapper (vendor registration + interception) | Task 1 |
| 3 | Tushare provider | Task 2 |
| 4 | AKShare provider | Task 2 |
| 5 | BaoStock provider | Task 2 |
| 6 | Chinese news + sentiment | Task 2 |
| 7 | Agent Prompt Chinese enhancement | Task 1 |
| 8 | PostgreSQL cache layer | Task 2 |
| 9 | Markdown report export | Task 7 |
| 10 | Batch analysis runner | Task 2 |
| 11 | Dependencies + integration | All |
