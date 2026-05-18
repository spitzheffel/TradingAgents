# TradingAgents 中文适配与 A 股支持 — 设计规格

## 概述

在 fork 的 TradingAgents v0.2.5 上以**纯插件式**架构实现中国市场支持。核心原则：零修改上游文件，所有功能通过运行时动态注册/monkey-patch 注入，确保 `git merge upstream/main` 无冲突。

## 插件架构

### 激活机制

新建模块 `tradingagents/cn_plugin/`，作为所有中国市场功能的统一入口：

```
tradingagents/cn_plugin/
├── __init__.py          # 插件激活入口，import 即生效
├── config.py            # CN 专属配置定义与合并
├── ticker.py            # Ticker 标准化与市场检测
├── routing.py           # 路由增强（A股检测 + 缓存注入）
├── dataflows/
│   ├── __init__.py
│   ├── tushare_provider.py
│   ├── akshare_provider.py
│   ├── baostock_provider.py
│   ├── eastmoney_news.py
│   ├── sina_news.py
│   └── sentiment.py
├── cache/
│   ├── __init__.py
│   ├── pg_client.py
│   ├── ohlcv_cache.py
│   ├── news_cache.py
│   └── schema.sql
├── prompts/
│   ├── __init__.py
│   └── zh_cn.py
├── reports/
│   ├── __init__.py
│   ├── markdown_report.py
│   └── templates/
└── batch/
    ├── __init__.py
    └── runner.py
```

激活方式：

```python
# CLI 启动时或用户代码中
import tradingagents.cn_plugin  # 一行激活全部功能
```

`cn_plugin/__init__.py` 内部按顺序执行：
1. 合并 CN 配置到全局 config
2. 注册 china vendor 到 `VENDOR_METHODS`
3. Monkey-patch `route_to_vendor` 注入 ticker 标准化 + 缓存
4. Monkey-patch `get_language_instruction` 注入中文增强指令

### 与上游的边界

| 上游文件 | 我们的做法 | 依赖的公开接口 |
|---------|-----------|--------------|
| `dataflows/interface.py` | 运行时追加 `VENDOR_LIST`/`VENDOR_METHODS`；wrap `route_to_vendor` | 模块级 list/dict 变量；函数签名 |
| `dataflows/config.py` | 调用 `set_config()` 合并 CN 配置 | `set_config(dict)` 函数 |
| `agents/utils/agent_utils.py` | Wrap `get_language_instruction` | 函数签名和返回值语义 |
| `default_config.py` | 不改；CN 配置在自己的 `config.py` 中 | `DEFAULT_CONFIG` 字典结构 |

**风险缓解**：如果上游重构了这些接口（概率低），我们的 `cn_plugin/__init__.py` 会在 import 时报错，定位清晰，修复成本低。

---

## 模块详细设计

### 1. Ticker 标准化（`cn_plugin/ticker.py`）

**输入格式支持：**
- `600519` → `600519.SH`
- `600519.SH` / `600519.sh` → `600519.SH`
- `SH600519` / `sh600519` → `600519.SH`
- `000858` → `000858.SZ`
- `300750` → `300750.SZ`
- `830799` → `830799.BJ`

**规则：**
- 60xxxx → .SH（上海主板）
- 000xxx / 001xxx / 002xxx / 003xxx → .SZ（深圳主板/中小板）
- 300xxx / 301xxx → .SZ（创业板）
- 4xxxxx / 8xxxxx → .BJ（北交所）
- 688xxx → .SH（科创板）

**市场检测函数：**
```python
def is_china_ticker(symbol: str) -> bool
def normalize_ticker(symbol: str) -> str  # 返回标准格式或原样返回
```

### 2. 路由增强（`cn_plugin/routing.py`）

Wrap 原始 `route_to_vendor`：

```python
def enhanced_route_to_vendor(method, *args, **kwargs):
    # 1. Ticker 标准化（如果第一个参数是 ticker）
    # 2. 如果是 A 股 ticker，强制使用 china vendor（忽略配置的 category vendor）
    # 3. 查缓存（如果 cache_enabled）
    # 4. Miss → 调原始 route_to_vendor 或 china provider
    # 5. 写回缓存
    # 6. 返回结果
```

### 3. 数据 Provider（`cn_plugin/dataflows/`）

#### 3.1 Tushare Provider（主）

需要 `TUSHARE_TOKEN` 环境变量。

| 接口 | Tushare API | 说明 |
|------|------------|------|
| `get_stock_data` | `pro.daily()` | OHLCV 日线 |
| `get_indicators` | 基于 OHLCV + stockstats | 复用原版 StockstatsUtils |
| `get_fundamentals` | `pro.daily_basic()` + `pro.stock_basic()` | PE/PB/总市值等 |
| `get_balance_sheet` | `pro.balancesheet()` | 资产负债表 |
| `get_cashflow` | `pro.cashflow()` | 现金流量表 |
| `get_income_statement` | `pro.income()` | 利润表 |
| `get_insider_transactions` | `pro.stk_holdertrade()` | 股东增减持 |

**返回格式**：与 yfinance provider 一致 — 带 header 注释的 CSV 字符串。

#### 3.2 AKShare Provider（降级备选）

免费，无需注册。

| 接口 | AKShare 函数 | 说明 |
|------|-------------|------|
| `get_stock_data` | `ak.stock_zh_a_hist()` | 东方财富日线 |
| `get_indicators` | 基于 OHLCV + stockstats | 同上 |
| `get_fundamentals` | `ak.stock_individual_info_em()` | 基本信息 |
| `get_balance_sheet` | `ak.stock_balance_sheet_by_report_em()` | 资产负债表 |
| `get_cashflow` | `ak.stock_cash_flow_sheet_by_report_em()` | 现金流 |
| `get_income_statement` | `ak.stock_profit_sheet_by_report_em()` | 利润表 |
| `get_insider_transactions` | `ak.stock_hold_management_detail_em()` | 高管持股变动 |

#### 3.3 BaoStock Provider（最终兜底）

免费，数据更新可能滞后 1 天。覆盖 OHLCV 和基本财务数据。

#### 3.4 降级链

```python
def get_stock_data_china(symbol, start_date, end_date):
    providers = [tushare, akshare, baostock]  # 按配置排序
    for provider in providers:
        try:
            result = provider.get_stock_data(symbol, start_date, end_date)
            if result and "No data" not in result:
                return result
        except Exception:
            continue
    return f"No data available for {symbol} from any China data source"
```

### 4. 中文新闻/情绪（`cn_plugin/dataflows/`）

#### 东方财富新闻（`eastmoney_news.py`）
- `ak.stock_news_em(symbol)` — 个股新闻
- `ak.news_cctv()` + `ak.news_economic_baidu()` — 宏观新闻

#### 新浪财经新闻（`sina_news.py`）
- 爬取新浪财经个股新闻列表
- 作为东方财富的补充源

#### 情绪数据（`sentiment.py`）
- `ak.stock_comment_em()` — 东方财富千股千评
- 股吧热度和情绪概览

### 5. PostgreSQL 缓存层（`cn_plugin/cache/`）

#### 连接管理（`pg_client.py`）
- 使用 psycopg3 连接池
- DSN 从环境变量 `TRADINGAGENTS_PG_DSN` 获取
- 连接失败时静默降级（cache miss，不阻塞分析）

#### 表结构（`schema.sql`）

```sql
-- 需要 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE ohlcv_daily (
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
SELECT create_hypertable('ohlcv_daily', 'trade_date');

CREATE TABLE fundamentals_cache (
    ticker TEXT NOT NULL,
    data_type TEXT NOT NULL,  -- 'fundamentals'/'balance_sheet'/'cashflow'/'income'
    report_date DATE,
    content TEXT NOT NULL,    -- 原始 CSV 字符串
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, data_type, report_date)
);

CREATE TABLE news_cache (
    id SERIAL PRIMARY KEY,
    ticker TEXT,              -- NULL for global news
    publish_date DATE NOT NULL,
    source TEXT NOT NULL,     -- 'eastmoney'/'sina'/'yfinance'
    content TEXT NOT NULL,    -- 原始返回字符串
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, publish_date, source)
);

CREATE TABLE analysis_reports (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    report_content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 缓存策略
- OHLCV：按 (ticker, date_range) 查询，命中则直接返回 CSV；永不过期
- 当日数据：TTL 15 分钟（通过 `fetched_at` 判断）
- 新闻：按 (ticker, date, source) 去重，同天不重复拉取
- 缓存 miss 或 PG 不可用 → 透传到实际 provider，不报错

### 6. Agent Prompt 中文化（`cn_plugin/prompts/`）

#### 增强机制

Wrap `get_language_instruction()`：当 `output_language` 为中文时，返回详细的中文指令块：

```python
ZH_INSTRUCTION = """
请使用简体中文撰写完整报告。遵循以下规范：

**术语对照**：
- PE Ratio → 市盈率，PB Ratio → 市净率
- Market Cap → 总市值，EPS → 每股收益
- Revenue → 营业收入，Net Income → 净利润
- ROE → 净资产收益率，Debt-to-Equity → 资产负债率
- MACD → MACD 指标，RSI → 相对强弱指标
- Bullish → 看多/多头，Bearish → 看空/空头

**格式要求**：
- 报告标题使用中文
- 数据表格保留数字精度
- 货币单位使用人民币（元/万元/亿元）
- 日期使用 YYYY-MM-DD 格式
- 百分比保留两位小数
"""
```

#### 全局新闻查询中文化

CN 配置中提供中文版 `global_news_queries`：
```python
"global_news_queries": [
    "央行 LPR 利率 货币政策",
    "A股 沪深 GDP 经济数据",
    "地缘政治 贸易摩擦 制裁",
    "美联储 欧央行 日央行 政策",
    "原油 大宗商品 供应链 能源",
]
```

### 7. Markdown 报告导出（`cn_plugin/reports/`）

#### 报告结构

```markdown
# {ticker} 投资分析报告
> 分析日期：{date} | 生成时间：{now}

## 摘要
{executive_summary}

## 基本面分析
{fundamentals_report}

## 技术面分析
{market_report}

## 新闻分析
{news_report}

## 市场情绪
{sentiment_report}

## 多空辩论
### 看多观点
{bull_research}
### 看空观点
{bear_research}
### 研究总监总结
{research_manager_summary}

## 交易建议
{trader_recommendation}

## 风险评估
{risk_assessment}

## 最终决策
{final_decision}
```

#### 集成方式

在分析完成后（`TradingAgentsGraph.propagate()` 返回后），从 state 中提取各 report 字段，组装为 Markdown 并保存。通过在分析流程末尾 hook 调用，不改上游 graph 代码。

### 8. 批量分析（`cn_plugin/batch/`）

#### 调度器（`runner.py`）

```python
async def run_batch(
    tickers: List[str],
    trade_date: str,
    config: dict,
    max_concurrency: int = 2,
) -> List[dict]:
    """并发执行多个 ticker 的分析，返回结果列表。"""
```

- 使用 `asyncio.Semaphore(max_concurrency)` 控制并发
- 每个 ticker 独立实例化 `TradingAgentsGraph`
- 失败的 ticker 记录错误但不阻塞其他
- 全部完成后生成汇总比较报告

#### CLI 命令

注册到 typer app（通过在 cli 启动时检测 cn_plugin 是否激活）：

```
tradingagents batch --tickers "600519.SH,000858.SZ,300750.SZ" --date 2025-05-16 --concurrency 2
tradingagents batch --file watchlist.txt --date 2025-05-16
```

---

## 配置汇总

CN 插件专属配置（`cn_plugin/config.py`）：

```python
CN_CONFIG = {
    # 数据源
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
    "china_data_priority": ["tushare", "akshare", "baostock"],

    # 缓存
    "cache_enabled": True,
    "cache_backend": "postgresql",
    "pg_dsn": os.getenv("TRADINGAGENTS_PG_DSN", "postgresql://localhost:5432/tradingagents"),
    "cache_ttl_intraday_minutes": 15,

    # 中文化
    "output_language": "Chinese",
    "global_news_queries": [...],  # 中文宏观关键词

    # 批量
    "batch_max_concurrency": 2,

    # 基准指数
    "benchmark_map_cn": {
        ".SH": "000001.SH",
        ".SZ": "399001.SZ",
        ".BJ": "899050.BJ",
    },
}
```

通过 `set_config(CN_CONFIG)` 合并到全局，不覆盖用户已设置的值。

---

## 依赖新增

```toml
# 可选依赖组，不污染原版安装
[project.optional-dependencies]
cn = [
    "tushare>=1.4.2",
    "akshare>=1.14.0",
    "baostock>=0.8.8",
    "psycopg[binary]>=3.2.0",
]
```

安装方式：`pip install -e ".[cn]"`

---

## 验证方案

1. **插件激活**：`import tradingagents.cn_plugin` 后，确认 `VENDOR_LIST` 包含 "china"，`route_to_vendor` 已被 wrap
2. **Ticker 标准化**：单元测试覆盖所有输入格式
3. **数据源**：脚本调用 `get_stock_data("600519.SH", "2025-05-01", "2025-05-16")`，验证 Tushare → AKShare 降级
4. **缓存**：同一请求第二次命中 PG，无 API 调用
5. **中文输出**：CLI 分析 A 股后检查报告语言
6. **上游兼容**：不导入 cn_plugin 时，原版 AAPL 分析行为不变
7. **批量**：`tradingagents batch --tickers "600519.SH,000858.SZ"` 生成两份报告
