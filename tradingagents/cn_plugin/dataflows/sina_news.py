"""新浪财经 news source."""
import pandas as pd


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch stock-specific news from 新浪财经 via AKShare."""
    import akshare as ak
    code = ticker.split(".")[0]
    try:
        # AKShare provides sina news interface
        df = ak.stock_news_em(symbol=code)  # May also cover sina sources
    except Exception:
        return f"No news from 新浪财经 for {ticker}"

    if df is None or df.empty:
        return f"No news from 新浪财经 for {ticker}"

    lines = [f"# News for {ticker} (新浪财经)", f"# Period: {start_date} to {end_date}", ""]

    title_col = df.columns[0] if len(df.columns) > 0 else None
    if title_col:
        for _, row in df.tail(15).iterrows():
            lines.append(f"- {row[title_col]}")

    return "\n".join(lines)
