"""Chinese market sentiment aggregation."""
import pandas as pd


def get_china_sentiment(ticker: str) -> str:
    """Aggregate Chinese sentiment data for a ticker.

    Sources: 东方财富千股千评 (stock_comment_em)
    """
    import akshare as ak
    code = ticker.split(".")[0]

    parts = [f"# Sentiment Data for {ticker}", f"# Source: 东方财富", ""]

    # 千股千评
    try:
        df = ak.stock_comment_em()
        if df is not None and not df.empty:
            # Filter for our stock
            code_col = None
            for col in df.columns:
                if "代码" in col or "code" in col.lower():
                    code_col = col
                    break

            if code_col:
                row = df[df[code_col].astype(str) == code]
                if not row.empty:
                    parts.append("## 千股千评")
                    for col in row.columns:
                        val = row.iloc[0][col]
                        parts.append(f"- {col}: {val}")
                else:
                    parts.append("千股千评: 未找到该股票数据")
            else:
                parts.append("千股千评: 数据格式异常")
        else:
            parts.append("千股千评: 无数据")
    except Exception as e:
        parts.append(f"千股千评: 获取失败 ({e})")

    return "\n".join(parts)
