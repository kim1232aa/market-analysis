---
name: market-analysis
description: >-
  多空分析 (加密货币永续 + A股个股) / long-short market analysis for BOTH crypto
  perpetuals and China A-shares, in one skill. Fetches REAL live data and outputs
  a ready-to-paste long/short readout with entry/stop/target scenarios. Auto-routes
  by symbol: a ticker like ETH/BTC/SOL (+ optional 5m/15m/1H) → crypto perp
  (OKX/Binance/Bybit: OI, funding, 多空比, taker, RSI/ATR, orderbook); a 6-digit
  code like 600519/000001/300750 (or sh600519) → A-share (东财/腾讯/新浪: 涨跌停,
  主力资金流, 龙虎榜, 换手/量比, MA/MACD/BOLL, 多周期共振). Use for 行情/走势/多空分析,
  a scalping/swing read, coin or stock screening, or mentions of 资金费率/持仓量/OI/
  多空比/funding OR 股票/A股/个股/龙虎榜/主力资金/北向. No API key, no deps.
---

# market-analysis — 加密永续 + A股 统一多空分析

One skill, two domains. `analyze.py` **auto-routes** by the symbol: crypto ticker
→ perp analysis; 6-digit code → A-share. Same anti-hallucination ethos both sides:
every number comes from the fetch script; failed sources are reported, never invented.

## Iron rules (do not break)

0. **SETUP = NONE. No API key, no pip install.** Python 3 stdlib only, over PUBLIC
   endpoints (crypto: OKX/Binance/Bybit · A股: 东财/腾讯/新浪). **NEVER ask the user
   for a key/token — none exists** (no `PERP_API_KEY`, this is not "Perpetual
   Protocol"). If data won't load it is network/geo/风控限流, not auth → retry or
   `HTTPS_PROXY`. Just run the script.
1. **NEVER write a number the script didn't output.** If `errors[]` is non-empty,
   say which source failed. Scripts auto-fall back across sources; don't fabricate.
2. **FORCED OUTPUT + PROOF-OF-RUN.** The whole 报告块 (between `╔═══╗` and `╚═══╝`)
   MUST appear verbatim — do NOT compress the 面板表 into prose, drop rows, or omit
   合并结论/建议. **AND you MUST also paste the script's `----- JSON -----` block as
   proof you actually ran it.** A report WITHOUT that JSON anchor = you did NOT run
   the script = a FABRICATED report — never deliver one, run the script instead.
   (You cannot fabricate the exact JSON; that is exactly why it is required.)
3. **Always end with a risk line.** 技术分析 not 投资建议; every scenario carries a
   stop-loss + control-leverage note. A股 must also flag **T+1 & 涨跌停板**.
4. **Reply in the user's language** (中文/日本語 — never English).
5. Data is a snapshot; prices move. Offer to re-run / monitor.

## Step 1 — Run it (auto-routes)

```bash
python3 <skill_dir>/scripts/analyze.py ETH 5m     # 加密永续 (ETH/BTC/SOL... + 周期)
python3 <skill_dir>/scripts/analyze.py 600519     # A股个股 (600519/000001/300750/sh600519)
```
- Detection: arg = 6 digits (optional sh/sz/bj) → A股; else → 加密。
- Windows: `python` not `python3`. Blocked exchanges → prefix `HTTPS_PROXY=http://<proxy>:<port>`.

Prints `DATA REPORT` + **`报告块`(your deliverable)** + `JSON`.

## Step 2 — What each domain reports (the script tags all this)

**加密永续** (crypto): 多周期共振(5m/15m/1H/4H) · 资金费率/基差 · **OI×价** · 散户多空比(反指)
· **大户持仓比**(主力) · taker · RSI/ATR · 盘口失衡 · 跨所资金费(OKX/Binance/Bybit)。总开关=swing_low。
Weight: 共振≈OI×价≈大户持仓≈taker > 结构/RSI > 盘口 > 散户(反指) > 资金费。

**A股** (stock): 涨跌停状态 · **主力资金流**(超大/大/中/小单, 东财;缺则新浪) · **龙虎榜**(机构vs游资/净买)
· 量价(量比) · 均线(MA5/10/20/60=生命线) · MACD · RSI · BOLL · 多周期共振(60分/日/周/月)。总开关=MA20。
Weight: 主力资金流≈涨跌停/均线≈量价 > MACD/RSI > 换手 > 估值。**必带 T+1 & 涨跌停 提醒。**

细则见 `scripts/crypto/analyze.py --help` 和 `scripts/ashare/analyze.py --help`。

## Step 3 — Output (user's language)
Relay the ENTIRE 报告块 verbatim (面板表/合并结论/建议不可删), add 2~4 lines 关键信号解读
(谁在买卖/是否游资博弈/趋势转折), reinforce the script's 建议, end with risk line.

## 找标的 (扫描)
```bash
python3 scripts/scan.py ashare [N]              # A股: 全市场龙虎榜×资金流找强势股
python3 scripts/scan.py crypto BTC,ETH,SOL 15m  # 加密: watchlist按评分排名
```
监控(仅加密): `scripts/crypto/alert.py SYM SUPPORT RESISTANCE` (配 /loop 5m)。

## Not on Claude Code?
Cross-agent (Codex/OpenClaw/Hermes) — SKILL.md standard, same folder. Or just run the
scripts (no harness needed). See AGENTS.md. Report block between `╔═╗` = mandatory verbatim.
