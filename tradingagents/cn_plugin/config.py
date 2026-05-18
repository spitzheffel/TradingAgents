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
