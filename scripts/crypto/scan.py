#!/usr/bin/env python3
"""
scan.py :: batch watchlist scanner. Ranks coins by 机械评分 to surface setups.

Usage:
    python3 scan.py                       # default list, 15m
    python3 scan.py ETH,BTC,SOL,BNB 5m
    python3 scan.py BTC,ETH,SOL,DOGE,XRP,AVAX,LINK 1H
"""
import sys
import perp_core as pc

HELP = """scan.py — 多币批量扫描,按机械评分排名找 setup(实时真实数据)

用法: python3 scan.py [SYM1,SYM2,...] [BAR]
  默认: BTC,ETH,SOL,BNB,XRP,DOGE  15m
  例:   python3 scan.py ETH,BTC,SOL 5m

输出: 排名表(偏多在上): 现价/24h%/RSI/评分/基调/主导信号,并点名最偏多·最偏空。
只有核心衍生品数据齐全(资金费/OI/散户多空比/大户持仓比/Taker)的币才参与评分排名;
数据不全的币单独列出,不与完整评分的币混排。轻量版(仅价格+衍生品,不含盘口/多周期)。
深入某币: python3 analyze.py <SYM> <BAR>
铁律: 只用真实数据,失败=数据不足不编造; 评分为量化参考·非投资建议。"""


def _missing_primary_derivs(dv):
    dv = dv or {}
    required = {
        "资金费": dv.get("funding_rate_8h"), "OI": dv.get("oi_usd"),
        "散户多空比": (dv.get("global_ls") or {}).get("ratio"),
        "大户持仓比": (dv.get("top_position") or {}).get("ratio"),
        "Taker": (dv.get("taker_buysell") or {}).get("last"),
    }
    return [name for name, value in required.items() if value is None]


def main(argv):
    if len(argv) > 0 and argv[0] in ("-h", "--help", "help"):
        print(HELP); return 0

    syms = (argv[0].upper().split(",") if len(argv) > 0
            else ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"])
    bar = argv[1] if len(argv) > 1 else "15m"
    period = bar if bar in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"} else "15m"

    results = []
    for s in syms:
        errs = []
        price = pc.okx_price(s, errs)
        cd = pc.okx_candles(s, bar, 60, errs)
        lv = pc.build_levels(cd)
        dv = pc.bn_derivs(s, period, errs)
        if not price or not lv:
            results.append((s, None, None, None, None, None, "数据不足/获取失败")); continue
        missing = _missing_primary_derivs(dv)
        rows, total, bias = pc.signal_rows(price["last"], lv, dv)
        if missing:
            # Core derivatives missing -- do not let a partially-populated score
            # (missing legs silently scoring 0) rank alongside fully-scored coins.
            results.append((s, price["last"], price["chg24h_pct"], lv.get("rsi14"), None, "数据不全·不参与排名",
                            "核心缺失：" + "、".join(missing)))
            continue
        # one-line reason: strongest 2 signals
        strong = sorted(rows, key=lambda r: -abs(r[3]))[:2]
        reason = " / ".join(f"{r[0]}:{r[2]}" for r in strong if r[3] != 0) or "信号平淡"
        results.append((s, price["last"], price["chg24h_pct"], lv.get("rsi14"), total, bias, reason))

    # rank: bullish first (desc score); missing/failed rows last, never ranked
    ok = [r for r in results if r[4] is not None]
    bad = [r for r in results if r[4] is None]
    ok.sort(key=lambda r: -r[4])
    g = pc._fmt

    print(f"===== 多币扫描 · {bar} · 按机械评分排名(偏多在上) =====\n")
    print("| 排名 | 币 | 现价 | 24h% | RSI | 评分 | 基调 | 主导信号 |")
    print("|---|---|---|---|---|---|---|---|")
    for i, (s, p, c, r, t, b, reason) in enumerate(ok, 1):
        print(f"| {i} | {s} | {g(p)} | {g(c)} | {g(r,0)} | {g(t)} | {b} | {reason} |")
    for s, p, c, r, _t, b, reason in bad:
        print(f"| — | {s} | {g(p)} | {g(c)} | {g(r,0)} | — | {b or '—'} | {reason} |")

    if ok:
        top, bot = ok[0], ok[-1]
        print(f"\n**最偏多：{top[0]} (评分 {g(top[4])}, {top[5]})** ｜ **最偏空：{bot[0]} (评分 {g(bot[4])}, {bot[5]})**")
        print(f"→ 想深入看某个币: `python3 analyze.py {top[0]} {bar}`")
    print("\n⚠️ 评分为量化参考·非投资建议。扫描仅用价格+衍生品(未含盘口/多周期),深入分析请用 analyze.py。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
