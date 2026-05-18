"""BaoStock data provider — free, no token required, data may lag 1 day.

BaoStock is the final fallback in the chain: Tushare → AKShare → BaoStock.
Ticker format: sh.600519 or sz.000858 (lowercase prefix + dot + code).
"""

import pandas as pd
import baostock as bs
from stockstats import wrap


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_bs_code(symbol: str) -> str:
    """Convert 600519.SH to sh.600519 format."""
    parts = symbol.split(".")
    if len(parts) != 2:
        return symbol
    code, exchange = parts[0], parts[1].lower()
    return f"{exchange}.{code}"


def _ensure_login():
    """Login to BaoStock (idempotent, re-login if needed)."""
    lg = bs.login()
    if lg.error_code != '0':
        raise ConnectionError(f"BaoStock login failed: {lg.error_msg}")


def _query_to_df(rs) -> pd.DataFrame:
    """Convert BaoStock ResultSet to DataFrame."""
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    return pd.DataFrame(rows, columns=rs.fields)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Return OHLCV data as a CSV string with metadata header."""
    _ensure_login()
    bs_code = _to_bs_code(symbol)
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2",  # 前复权
    )
    df = _query_to_df(rs)
    if df.empty:
        return f"No data found for {symbol} between {start_date} and {end_date}"

    df = df.rename(columns={
        "date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").astype("Int64")

    csv_string = df.to_csv(index=False)
    header = (
        f"# Stock data for {symbol} from {start_date} to {end_date}\n"
        f"# Total records: {len(df)}\n"
        f"# Source: BaoStock\n\n"
    )
    return header + csv_string


def get_indicators(symbol: str, start_date: str, end_date: str) -> str:
    """Return technical indicators computed from BaoStock OHLCV data."""
    _ensure_login()
    bs_code = _to_bs_code(symbol)
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2",
    )
    df = _query_to_df(rs)
    if df.empty:
        return f"No indicator data for {symbol}"

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    stock_df = wrap(df)

    indicators = [
        "macd", "macds", "macdh",
        "rsi_14",
        "close_50_sma", "close_10_ema",
        "boll", "boll_ub", "boll_lb",
    ]
    results = [
        f"# Technical Indicators for {symbol}",
        f"# Source: BaoStock",
        "",
    ]
    for ind in indicators:
        try:
            stock_df[ind]
            val = stock_df[ind].iloc[-1]
            results.append(f"{ind}: {val:.4f}" if pd.notna(val) else f"{ind}: N/A")
        except Exception:
            results.append(f"{ind}: N/A")
    return "\n".join(results)


def get_fundamentals(symbol: str) -> str:
    """Return basic stock info from BaoStock."""
    _ensure_login()
    bs_code = _to_bs_code(symbol)
    rs = bs.query_stock_basic(code=bs_code)
    df = _query_to_df(rs)
    if df.empty:
        return f"No fundamentals data for {symbol} (BaoStock)"
    header = f"# Fundamentals for {symbol}\n# Source: BaoStock\n\n"
    return header + df.to_csv(index=False)


def get_balance_sheet(symbol: str) -> str:
    """Return the 4 most recent balance sheet records."""
    _ensure_login()
    bs_code = _to_bs_code(symbol)
    rs = bs.query_balance_data(code=bs_code)
    df = _query_to_df(rs)
    if df.empty:
        return f"No balance sheet data for {symbol} (BaoStock)"
    df = df.head(4)
    header = f"# Balance Sheet for {symbol}\n# Source: BaoStock\n\n"
    return header + df.to_csv(index=False)


def get_cashflow(symbol: str) -> str:
    """Return the 4 most recent cash flow records."""
    _ensure_login()
    bs_code = _to_bs_code(symbol)
    rs = bs.query_cash_flow_data(code=bs_code)
    df = _query_to_df(rs)
    if df.empty:
        return f"No cashflow data for {symbol} (BaoStock)"
    df = df.head(4)
    header = f"# Cash Flow for {symbol}\n# Source: BaoStock\n\n"
    return header + df.to_csv(index=False)


def get_income_statement(symbol: str) -> str:
    """Return the 4 most recent income statement records."""
    _ensure_login()
    bs_code = _to_bs_code(symbol)
    rs = bs.query_profit_data(code=bs_code)
    df = _query_to_df(rs)
    if df.empty:
        return f"No income statement data for {symbol} (BaoStock)"
    df = df.head(4)
    header = f"# Income Statement for {symbol}\n# Source: BaoStock\n\n"
    return header + df.to_csv(index=False)


def get_insider_transactions(symbol: str) -> str:
    """BaoStock does not provide insider transaction data."""
    return f"Insider transaction data not available from BaoStock for {symbol}"
