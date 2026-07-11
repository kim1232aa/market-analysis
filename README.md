# market-analysis

A [Claude Code](https://claude.com/claude-code) **Skill** (also Codex / OpenClaw /
Hermes / bare terminal) for **long/short analysis of crypto perpetuals AND China
A-shares — in one skill**. `analyze.py` auto-routes by the symbol. Built to stop
agents **hallucinating prices/indicators**: every number comes from a fetch script;
failed sources are reported, never invented.

```bash
python3 scripts/analyze.py ETH 5m     # → 加密永续 (OKX/Binance/Bybit)
python3 scripts/analyze.py 600519     # → A股个股 (东财/腾讯/新浪)
```
Detection: 6-digit code (± `sh`/`sz`/`bj`) → A股; else → crypto.

## What it does

**加密永续** — 多周期共振(5m/15m/1H/4H) · 资金费率/基差 · OI×价 · 散户多空比(反指) ·
大户持仓比(主力) · taker · RSI/ATR · 盘口失衡 · 跨所资金费(OKX/Binance/Bybit)。

**A股个股** — 涨跌停状态 · 主力资金流(超大/大/中/小单) · 龙虎榜(机构vs游资) · 量价/换手/量比 ·
MA5/10/20/60 · MACD · BOLL · RSI · ATR · 多周期共振(60分/日/周/月) · T+1/涨跌停 融入情景剧本。

Both output a forced, ready-to-paste 报告块 with 机械评分 + 情景剧本(进场/止损/目标/RR) + 合并结论/建议.

## Tools (`scripts/`)
| Script | Purpose |
|---|---|
| `analyze.py <symbol> [tf]` | 统一入口, 自动分流加密/A股 (主要工具) |
| `scan.py ashare [N]` | A股: 全市场龙虎榜×主力资金流找强势股 |
| `scan.py crypto <SYMS> [BAR]` | 加密: watchlist按机械评分排名 |
| `crypto/alert.py SYM SUP RES` | 加密触发位监控 (配 /loop) |
| `crypto/backtest.py` · `ashare/backtest.py` | 本地OHLC决策日志回测(次K开盘价成交,无未来函数;独立执行层实验,非实时分析一部分) |
| `crypto/` · `ashare/` | 两域各自的 core + analyze (被分发器调用) |

- **Python stdlib only** — no deps, no API keys. Multi-source auto-fallback per domain.
- 交易所被墙/风控 → 前缀 `HTTPS_PROXY=http://<proxy>:<port>`.

## Install (Claude Code / Codex / OpenClaw / Hermes)
`SKILL.md` is a cross-agent standard — same folder, different dir per harness:

| Harness | Skill dir | Install |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `bash install.sh claude` |
| Codex CLI | `~/.codex/skills/` | `bash install.sh codex` |
| OpenClaw | `~/.openclaw/skills/` | `bash install.sh openclaw` |
| Hermes | `~/.hermes/skills/` | `bash install.sh hermes` |

```bash
curl -fsSL https://raw.githubusercontent.com/kim1232aa/market-analysis/main/install.sh | bash
# or all at once:  bash install.sh all
```
Restart the agent after install. Or just run the scripts directly — no harness needed.

> Supersedes the separate `crypto-perp-analysis` and `ashare-analysis` skills (merged here).

## Disclaimer
技术分析, **非投资建议**——脚本不会自动下单，这是工具输出层面的定位，不是禁止使用者(人或agent)在被
直接问到时给出自己的判断。加密低时间级别噪音大；**A股 T+1 & 涨跌停板**有实际约束。务必带止损、控制仓位。
数据为实时快照，随时变动。R:R 为结构测算，非承诺胜率。核心数据缺失时 `建议(主策略)` 会显示
`NO_TRADE·数据不足` 而不是编一个方向。

## License
MIT
