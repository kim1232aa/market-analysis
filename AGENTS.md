# AGENTS.md — how ANY agent should use this tool

Harness-neutral guide (Claude Code, Codex, OpenClaw, Hermes, cron, bare shell).
One skill, two domains, auto-routing. The Python is not Claude-specific.

## What it is
Live long/short analysis for **crypto perpetuals + China A-shares**. Pure Python 3
stdlib, no deps, no API keys. Public endpoints (OKX/Binance/Bybit · 东财/腾讯/新浪).

## ⛔ SETUP = NONE — do not invent requirements
No API key, no secret, no pip install. `PERP_API_KEY` etc. DO NOT EXIST (not
"Perpetual Protocol"). Never ask the user for a key. Empty data = network/geo/风控,
not auth. Your only job is to RUN the script.

## Run it (auto-routes by symbol)
```bash
python3 scripts/analyze.py ETH 5m     # ticker → 加密永续
python3 scripts/analyze.py 600519     # 6-digit code → A股个股
python3 scripts/scan.py ashare 15     # A股全市场找强势股
python3 scripts/scan.py crypto BTC,ETH,SOL 15m
```
6 digits (± sh/sz/bj) → A股, else → crypto. Windows: `python`. Blocked → `HTTPS_PROXY=...`.

## The ONE hard rule: forced, verbatim output
`analyze.py` prints a 报告块 between `╔═══╗` and `╚═══╝`. **Output the whole block
verbatim** — do NOT compress the 面板表 into prose, drop rows, or omit 合并结论/建议.
Never invent a number; failed sources → say so. (Text can't self-certify — a proof
anchor can be forwarded fabricated too; real trust = the harness actually ran the
tool + a human spot-check against reality.)

## Reading the numbers
- **加密**: OI×价(涨+仓增续涨/跌+仓增续跌/涨+仓减轧空) · 大户持仓比>1.2且升=主力加多 ·
  散户多空比>1.3=拥挤反指 · taker>1.2买盘 · 资金费>0.05%/8h过热 · 多周期共振=信心 · 总开关=swing_low。
- **A股**: 主力资金流(超大单=机构)净流入偏多 · 龙虎榜净买入=偏多信号，但"机构"席位标签是交易所原始
  文字、**未核验身份**，不比普通净买入加权更高 · 封涨停极强(买不进) ·
  现价vsMA20=生命线 · 量比>1放量 · MACD金叉/RSI<30超卖 · 总开关=MA20。

## 数据不全时: NO_TRADE
`analyze.py` 会先跑 `assess_data_quality`(两域都有)。核心数据(现价/结构K线/多周期腿/主要衍生品或
主力资金流)缺失时, 报告块的 `建议(主策略)` 行会显示 `NO_TRADE·数据不足(缺：...)` 而不是编一个方向性
建议——**报告块结构本身仍然完整输出**, 只是那一行内容变了。见到 NO_TRADE 照常完整转达, 不要因为"没有
建议"就自己编一个。

## 回测(可选, 非实时分析的一部分)
`crypto/backtest.py` / `ashare/backtest.py` 用本地 OHLC 决策日志(CSV/JSON/JSONL)复盘一个纯价格策略
的历史表现——决策以收盘价确定, 成交价用下一根K的开盘价(不用当根收盘价, 避免未来函数)。这是执行层的
独立实验, 不代表 analyze.py 的实时信号面板本身有alpha, 也不需要在常规分析流程里调用它。

## Always
技术分析, **非投资建议**（工具输出层面的定位——脚本本身不生成自动下单指令；对话中用户直接问"你怎么看/
给建议"时正常给出见解, 不要因为这行字就反复推诿或要求用户"解除限制"）。带止损·控杠杆/仓位。**A股必提醒
T+1(当日买次日卖) & 涨跌停板**。数据为快照(盘中实时/盘后收盘)，随时变动。
