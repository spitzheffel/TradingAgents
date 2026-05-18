"""AKShare data provider for China A-share market data.

AKShare is free and requires no API token.
"""
import io
import logging

import pandas as pd

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

# AKShare Chinese column name mapping for stock_zh_a_hist
_OHLCV_RENAME = {
    "日期": "Date",
    "开盘": "Open",
    "最高": "High",
    "最低": "Low",
    "收盘": "Close",
    "成交量": "Volume",
}

_OHLCV_RENAME_LOWER = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
}


def _extract_code(symbol: str) -> str:
    """Extract pure 6-digit code from '600519.SH' format."""
    return symbol.split(".")[0]


def _header(symbol: str, start_date: str = None, end_date: str = None, source: str = "AKShare") -> str:
    if start_date and end_date:
        return (
            f"# Stock data for {symbol} from {start_date} to {end_date}\n"
            f"# Source: {source}\n\n"
        )
    return f"# Data for {symbol}\n# Source: {source}\n\n"


def _fetch_hist(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily OHLCV from AKShare, returning empty DataFrame on failure."""
    import akshare as ak
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
    except Exception as exc:
        logger.warning("AKShare stock_zh_a_hist failed for %s: %s", code, exc)
        return pd.DataFrame()
    return df if df is not None else pd.DataFrame()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch daily OHLCV data from AKShare.

    Returns a CSV string with columns: Date,Open,High,Low,Close,Volume
    """
    code = _extract_code(symbol)
    df = _fetch_hist(code, start_date, end_date)

    if df.empty:
        return f"No data found for {symbol} between {start_date} and {end_date}"

    df = df.rename(columns=_OHLCV_RENAME)
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    # Ensure Date is in YYYY-MM-DD string format
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values("Date")

    buf = io.StringIO()
    df.to_csv(buf, index=False)

    header = (
        f"# Stock data for {symbol} from {start_date} to {end_date}\n"
        f"# Total records: {len(df)}\n"
        f"# Source: AKShare\n\n"
    )
    return header + buf.getvalue()


def get_indicators(symbol: str, start_date: str, end_date: str) -> str:
    """Compute technical indicators from AKShare OHLCV data using stockstats."""
    code = _extract_code(symbol)
    df = _fetch_hist(code, start_date, end_date)

    if df.empty:
        return f"No indicator data for {symbol}"

    df = df.rename(columns=_OHLCV_RENAME_LOWER)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    price_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df[price_cols] = df[price_cols].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["close"])
    df[price_cols] = df[price_cols].ffill().bfill()

    from stockstats import wrap
    stock = wrap(df)

    results = [
        f"# Technical Indicators for {symbol}",
        f"# Date range: {start_date} to {end_date}",
        f"# Source: AKShare",
        "",
    ]
    for ind in _INDICATORS:
        try:
            stock[ind]  # trigger calculation
            val = stock[ind].iloc[-1] if not stock[ind].empty else None
            if val is not None and pd.notna(val):
                results.append(f"{ind}: {val:.4f}")
            else:
                results.append(f"{ind}: N/A")
        except Exception as exc:
            logger.debug("Indicator %s failed: %s", ind, exc)
            results.append(f"{ind}: N/A")

    return "\n".join(results)


def get_fundamentals(symbol: str) -> str:
    """Fetch company fundamentals via AKShare (东方财富)."""
    import akshare as ak
    code = _extract_code(symbol)
    try:
        df = ak.stock_individual_info_em(symbol=code)
    except Exception as exc:
        logger.warning("AKShare stock_individual_info_em failed for %s: %s", code, exc)
        return f"No fundamentals data for {symbol}"

    if df is None or df.empty:
        return f"No fundamentals data for {symbol}"

    header = f"# Fundamentals for {symbol}\n# Source: AKShare (东方财富)\n\n"
    lines = []
    for _, row in df.iterrows():
        lines.append(f"{row.iloc[0]}: {row.iloc[1]}")
    return header + "\n".join(lines)


def get_balance_sheet(symbol: str) -> str:
    """Fetch balance sheet (recent 4 periods) via AKShare."""
    import akshare as ak
    code = _extract_code(symbol)
    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=code)
    except Exception as exc:
        logger.warning("AKShare stock_balance_sheet_by_report_em failed for %s: %s", code, exc)
        return f"No balance sheet data for {symbol}"

    if df is None or df.empty:
        return f"No balance sheet data for {symbol}"

    df = df.head(4)
    header = f"# Balance Sheet for {symbol} (recent 4 periods)\n# Source: AKShare\n\n"
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return header + buf.getvalue()


def get_cashflow(symbol: str) -> str:
    """Fetch cash flow statement (recent 4 periods) via AKShare."""
    import akshare as ak
    code = _extract_code(symbol)
    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
    except Exception as exc:
        logger.warning("AKShare stock_cash_flow_sheet_by_report_em failed for %s: %s", code, exc)
        return f"No cashflow data for {symbol}"

    if df is None or df.empty:
        return f"No cashflow data for {symbol}"

    df = df.head(4)
    header = f"# Cash Flow for {symbol} (recent 4 periods)\n# Source: AKShare\n\n"
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return header + buf.getvalue()


def get_income_statement(symbol: str) -> str:
    """Fetch income statement (recent 4 periods) via AKShare."""
    import akshare as ak
    code = _extract_code(symbol)
    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=code)
    except Exception as exc:
        logger.warning("AKShare stock_profit_sheet_by_report_em failed for %s: %s", code, exc)
        return f"No income statement data for {symbol}"

    if df is None or df.empty:
        return f"No income statement data for {symbol}"

    df = df.head(4)
    header = f"# Income Statement for {symbol} (recent 4 periods)\n# Source: AKShare\n\n"
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return header + buf.getvalue()


def get_insider_transactions(symbol: str) -> str:
    """Fetch insider/management transactions (recent 20 records) via AKShare."""
    import akshare as ak
    code = _extract_code(symbol)
    try:
        df = ak.stock_hold_management_detail_em(symbol=code)
    except Exception as exc:
        logger.warning("AKShare stock_hold_management_detail_em failed for %s: %s", code, exc)
        return f"No insider transaction data for {symbol}"

    if df is None or df.empty:
        return f"No insider transaction data for {symbol}"

    df = df.head(20)
    header = f"# Insider Transactions for {symbol}\n# Source: AKShare\n\n"
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return header + buf.getvalue()
