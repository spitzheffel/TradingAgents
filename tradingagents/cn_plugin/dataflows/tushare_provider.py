"""Tushare data provider for China A-share market data."""
import io
import logging
from typing import Optional

import pandas as pd

from tradingagents.cn_plugin.config import CN_CONFIG

logger = logging.getLogger(__name__)

# Indicators to compute via stockstats
_INDICATORS = [
    "macd",
    "macds",
    "macdh",
    "rsi_14",
    "close_50_sma",
    "close_10_ema",
    "boll",
    "boll_ub",
    "boll_lb",
]


def _get_pro():
    """Return a Tushare Pro API instance, raising ValueError if token is missing."""
    token = CN_CONFIG.get("tushare_token", "")
    if not token:
        raise ValueError("TUSHARE_TOKEN not configured")
    import tushare as ts
    ts.set_token(token)
    return ts.pro_api()


def _fmt_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD."""
    return date_str.replace("-", "")


def _header(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    if start_date and end_date:
        return (
            f"# Stock data for {symbol} from {start_date} to {end_date}\n"
            f"# Source: Tushare\n\n"
        )
    return f"# Data for {symbol}\n# Source: Tushare\n\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch daily OHLCV data from Tushare.

    Returns a CSV string with columns: Date,Open,High,Low,Close,Volume
    """
    pro = _get_pro()
    df = pro.daily(
        ts_code=symbol,
        start_date=_fmt_date(start_date),
        end_date=_fmt_date(end_date),
    )

    if df is None or df.empty:
        return _header(symbol, start_date, end_date) + "No data available"

    # Tushare daily returns: ts_code, trade_date, open, high, low, close, vol, ...
    df = df.rename(columns={
        "trade_date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "vol": "Volume",
    })

    # Normalise date format to YYYY-MM-DD
    df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date")

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return _header(symbol, start_date, end_date) + buf.getvalue()


def get_indicators(symbol: str, start_date: str, end_date: str) -> str:
    """Compute technical indicators from Tushare OHLCV data.

    Fetches OHLCV via get_stock_data, then uses stockstats to compute
    indicators without touching yfinance.
    """
    raw = get_stock_data(symbol, start_date, end_date)

    # Strip header lines (start with #)
    csv_lines = [l for l in raw.splitlines() if not l.startswith("#")]
    csv_text = "\n".join(csv_lines).strip()

    if not csv_text or "No data" in csv_text:
        return _header(symbol, start_date, end_date) + "No data available"

    df = pd.read_csv(io.StringIO(csv_text))
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    price_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df[price_cols] = df[price_cols].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["Close"])
    df[price_cols] = df[price_cols].ffill().bfill()

    from stockstats import wrap
    stock = wrap(df)

    # Use the last available row for indicator values
    results = []
    for ind in _INDICATORS:
        try:
            stock[ind]  # trigger calculation
            val = stock[ind].iloc[-1] if not stock[ind].empty else "N/A"
        except Exception as exc:
            logger.debug("Indicator %s failed: %s", ind, exc)
            val = "N/A"
        results.append(f"{ind}: {val}")

    return _header(symbol, start_date, end_date) + "\n".join(results)


def get_fundamentals(symbol: str) -> str:
    """Fetch basic fundamentals: PE, PB, market cap, and company info."""
    pro = _get_pro()

    # daily_basic gives valuation metrics for the latest trading day
    basic_df = pro.daily_basic(ts_code=symbol, fields="ts_code,trade_date,pe,pb,total_mv,circ_mv")
    if basic_df is None or basic_df.empty:
        basic_info = "No valuation data available"
    else:
        row = basic_df.iloc[0]
        basic_info = (
            f"Trade Date: {row.get('trade_date', 'N/A')}\n"
            f"PE Ratio: {row.get('pe', 'N/A')}\n"
            f"PB Ratio: {row.get('pb', 'N/A')}\n"
            f"Total Market Cap (万元): {row.get('total_mv', 'N/A')}\n"
            f"Circulating Market Cap (万元): {row.get('circ_mv', 'N/A')}"
        )

    # stock_basic gives company name, industry, etc.
    info_df = pro.stock_basic(ts_code=symbol, fields="ts_code,name,industry,area,list_date")
    if info_df is None or info_df.empty:
        company_info = "No company info available"
    else:
        row = info_df.iloc[0]
        company_info = (
            f"Name: {row.get('name', 'N/A')}\n"
            f"Industry: {row.get('industry', 'N/A')}\n"
            f"Area: {row.get('area', 'N/A')}\n"
            f"List Date: {row.get('list_date', 'N/A')}"
        )

    return (
        _header(symbol)
        + "=== Company Info ===\n"
        + company_info
        + "\n\n=== Valuation ===\n"
        + basic_info
    )


def get_balance_sheet(symbol: str) -> str:
    """Fetch balance sheet data (recent 4 periods)."""
    pro = _get_pro()
    fields = (
        "ts_code,ann_date,end_date,"
        "total_assets,total_liab,total_hldr_eqy_exc_min_int,"
        "money_cap,accounts_receiv,inventories"
    )
    df = pro.balancesheet(ts_code=symbol, fields=fields)

    if df is None or df.empty:
        return _header(symbol) + "No balance sheet data available"

    df = df.sort_values("end_date", ascending=False).head(4)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return _header(symbol) + buf.getvalue()


def get_cashflow(symbol: str) -> str:
    """Fetch cash flow statement data (recent 4 periods)."""
    pro = _get_pro()
    fields = (
        "ts_code,ann_date,end_date,"
        "net_profit,finan_exp,c_fr_oper_a,c_inf_fr_disp_subs_oper,"
        "c_paid_goods_s,n_cashflow_act,n_cash_flows_fnc_act"
    )
    df = pro.cashflow(ts_code=symbol, fields=fields)

    if df is None or df.empty:
        return _header(symbol) + "No cash flow data available"

    df = df.sort_values("end_date", ascending=False).head(4)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return _header(symbol) + buf.getvalue()


def get_income_statement(symbol: str) -> str:
    """Fetch income statement data (recent 4 periods)."""
    pro = _get_pro()
    fields = (
        "ts_code,ann_date,end_date,"
        "total_revenue,revenue,total_cogs,operate_profit,"
        "total_profit,income_tax,n_income,basic_eps"
    )
    df = pro.income(ts_code=symbol, fields=fields)

    if df is None or df.empty:
        return _header(symbol) + "No income statement data available"

    df = df.sort_values("end_date", ascending=False).head(4)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return _header(symbol) + buf.getvalue()


def get_insider_transactions(symbol: str) -> str:
    """Fetch shareholder trading records (recent 20 records)."""
    pro = _get_pro()
    df = pro.stk_holdertrade(ts_code=symbol)

    if df is None or df.empty:
        return _header(symbol) + "No insider transaction data available"

    df = df.head(20)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return _header(symbol) + buf.getvalue()
