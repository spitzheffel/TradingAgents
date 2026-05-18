"""东方财富 news via AKShare interface."""
import pandas as pd
from datetime import datetime, timedelta


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch stock-specific news from 东方财富 via AKShare."""
    import akshare as ak
    code = ticker.split(".")[0]
    try:
        df = ak.stock_news_em(symbol=code)
    except Exception:
        return f"No news data available for {ticker} from 东方财富"

    if df is None or df.empty:
        return f"No news found for {ticker} between {start_date} and {end_date}"

    # Filter by date range if date column exists
    if "发布时间" in df.columns:
        df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
        start_dt = pd.to_datetime(start_date)
        # Include the full end day (up to 23:59:59)
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df = df[(df["发布时间"] >= start_dt) & (df["发布时间"] <= end_dt)]

    if df.empty:
        return f"No news found for {ticker} between {start_date} and {end_date}"

    # Format output
    lines = [
        f"# News for {ticker} ({start_date} to {end_date})",
        f"# Source: 东方财富 (via AKShare)",
        f"# Total articles: {len(df)}",
        "",
    ]

    title_col = "新闻标题" if "新闻标题" in df.columns else df.columns[0]
    time_col = "发布时间" if "发布时间" in df.columns else None

    for _, row in df.head(30).iterrows():
        title = row.get(title_col, "")
        date_str = str(row.get(time_col, "")) if time_col else ""
        lines.append(f"- [{date_str}] {title}")

    return "\n".join(lines)


def get_global_news(curr_date: str, look_back_days: int = None, limit: int = None) -> str:
    """Fetch macro/global news from 东方财富 + CCTV."""
    import akshare as ak

    look_back = look_back_days or 7
    max_articles = limit or 20

    all_news = []

    # Source 1: CCTV news
    try:
        date_str = curr_date.replace("-", "")
        df = ak.news_cctv(date=date_str)
        if df is not None and not df.empty:
            title_col = "title" if "title" in df.columns else df.columns[0]
            for _, row in df.head(10).iterrows():
                all_news.append(f"[CCTV] {row.get(title_col, '')}")
    except Exception:
        pass

    # Source 2: Baidu economic news
    try:
        df = ak.news_economic_baidu()
        if df is not None and not df.empty:
            title_col = "title" if "title" in df.columns else df.columns[0]
            for _, row in df.head(10).iterrows():
                all_news.append(f"[百度财经] {row.get(title_col, '')}")
    except Exception:
        pass

    if not all_news:
        return f"No global news available for {curr_date}"

    lines = [
        f"# Global/Macro News as of {curr_date}",
        f"# Look back: {look_back} days",
        f"# Source: CCTV + 百度财经 (via AKShare)",
        "",
    ]
    lines.extend(all_news[:max_articles])

    return "\n".join(lines)
