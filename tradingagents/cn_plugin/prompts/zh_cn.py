"""Chinese prompt enhancement for trading agents."""

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
- Volume → 成交量，Turnover → 换手率
- Moving Average → 均线，Golden Cross → 金叉，Death Cross → 死叉

**格式要求**：
- 报告标题使用中文
- 数据表格保留数字精度
- 货币单位使用人民币（元/万元/亿元），如涉及美股则用美元
- 日期使用 YYYY-MM-DD 格式
- 百分比保留两位小数
- 末尾必须包含 Markdown 汇总表格
"""
