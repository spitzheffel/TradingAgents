CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ticker TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
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
