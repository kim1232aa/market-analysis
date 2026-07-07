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

## The ONE hard rule: forced output + proof-of-run
`analyze.py` prints a 报告块 between `╔═══╗` and `╚═══╝` ending with a **`🔒校验`
line** (real price/OI/funding/score + `sig` hash). **Output the whole block verbatim**
— do NOT compress the 面板表 into prose, drop rows, or omit 合并结论/建议. **The 🔒校验
line is MANDATORY proof-of-run — you can't fabricate it without running; a report
missing it = FAKE, never deliver one.** (Full `----- JSON -----` is optional to paste.)
Never invent a number; failed sources → say so.

## Reading the numbers
- **加密**: OI×价(涨+仓增续涨/跌+仓增续跌/涨+仓减轧空) · 大户持仓比>1.2且升=主力加多 ·
  散户多空比>1.3=拥挤反指 · taker>1.2买盘 · 资金费>0.05%/8h过热 · 多周期共振=信心 · 总开关=swing_low。
- **A股**: 主力资金流(超大单=机构)净流入偏多 · 龙虎榜机构买入=硬信号 · 封涨停极强(买不进) ·
  现价vsMA20=生命线 · 量比>1放量 · MACD金叉/RSI<30超卖 · 总开关=MA20。

## Always
技术分析, **非投资建议**。带止损·控杠杆/仓位。**A股必提醒 T+1(当日买次日卖) & 涨跌停板**。
数据为快照(盘中实时/盘后收盘)，随时变动。
