#!/usr/bin/env python3
"""
alert.py :: one-shot price-vs-trigger check for monitoring (wire into /loop).

Usage:
    python3 alert.py SYMBOL SUPPORT RESISTANCE [--confirm-closed BAR] [--profile P]
    python3 alert.py ETH 1785 1796
    python3 alert.py ETH 1785 1796 --confirm-closed 5m --profile conservative
Prints a single concise status line. Designed to be re-run every 5m by /loop:
the loop should surface the line and highlight when status starts with 🔴/🟢.

Default (no --confirm-closed): a LIVE-TICK WARNING only — the current price can
cross a level and reverse before any candle closes, so this is never printed as
a confirmed trading trigger. Pass --confirm-closed BAR to additionally check
whether N CLOSED candles (N from --profile, default balanced=1) have actually
closed beyond the level; only that path prints 🔴已收盘确认破位/🟢已收盘确认突破。
"""
import sys
import perp_core as pc

OKX_BAR = {"1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H", "1d": "1D"}

HELP = """alert.py — 触发位监控,一发式检查(配 /loop 做5分钟自动盯盘)

用法: python3 alert.py SYMBOL SUPPORT RESISTANCE [--confirm-closed BAR] [--profile P]
  例: python3 alert.py ETH 1785 1796
      python3 alert.py ETH 1785 1796 --confirm-closed 5m --profile conservative
默认(不带 --confirm-closed): 只给【实时预警】——实时价可能触位后又反转，不当作已收盘确认的交易触发。
  输出一行: ⚠️下破预警 / ⚠️上破预警 / ⚪区间内
带 --confirm-closed BAR: 额外检查最近 N 根已收盘 BAR K 是否真的收在位外(N=--profile决定,默认balanced=1根)，
  只有这条路径才会输出 🔴已收盘确认破位 / 🟢已收盘确认突破。
配合 /loop: /loop 5m python3 <path>/alert.py ETH 1785 1796
SUPPORT/RESISTANCE 通常取自 analyze.py 的 总开关支撑 / 突破阻力。"""


def main(argv):
    if len(argv) > 0 and argv[0] in ("-h", "--help", "help"):
        print(HELP); return 0
    if len(argv) < 3:
        print("用法: python3 alert.py SYMBOL SUPPORT RESISTANCE [--confirm-closed BAR] [--profile P]  (-h 看详情)")
        return 2

    sym = argv[0].upper()
    support = float(argv[1]); resistance = float(argv[2])
    rest = argv[3:]
    confirm_bar, profile_name = None, "balanced"
    i = 0
    while i < len(rest):
        if rest[i] == "--confirm-closed" and i + 1 < len(rest):
            confirm_bar = rest[i + 1].lower(); i += 2
        elif rest[i] == "--profile" and i + 1 < len(rest):
            profile_name = rest[i + 1]; i += 2
        else:
            i += 1
    if support >= resistance:
        print("参数错误：SUPPORT 必须小于 RESISTANCE"); return 2

    errs = []
    price = pc.okx_price(sym, errs)
    if not price or price.get("last") is None:
        print(f"⚠️ {sym} 价格获取失败(不要编造): {'; '.join(errs)}"); return 1
    last = price["last"]
    live_state = "breakdown" if last <= support else "breakout" if last >= resistance else None

    if not confirm_bar:
        if live_state == "breakdown":
            print(f"⚠️ 下破预警 {sym} {last} ≤ 支撑{support}：实时触价，未做已收盘确认；非交易触发。")
        elif live_state == "breakout":
            print(f"⚠️ 上破预警 {sym} {last} ≥ 阻力{resistance}：实时触价，未做已收盘确认；非交易触发。")
        else:
            pos = (last - support) / (resistance - support) * 100
            print(f"⚪区间内 {sym} {last}（支撑{support}~阻力{resistance}, 位置{pos:.0f}%）24h {price['chg24h_pct']:.2f}%")
        print("提示：如需已收盘确认，加 --confirm-closed 5m（可配 --profile）。")
        return 0

    try:
        profile = pc.profile_config(profile_name)
    except ValueError as e:
        print(f"参数错误：{e}"); return 2
    cd = pc.okx_candles(sym, OKX_BAR.get(confirm_bar, confirm_bar), max(5, profile["confirmed_closes"] + 2), errs)
    closes = cd["closes"] if cd else []
    confirmed = pc.level_confirmation(closes, support, resistance, profile["confirmed_closes"])
    close_text = "—" if not closes else f"{closes[-1]}（ts {cd['timestamps'][-1]}）"

    if confirmed == "breakdown":
        print(f"🔴 已收盘确认破位 {sym}：最近 {profile['confirmed_closes']} 根 {confirm_bar} K 收在支撑{support}下方（最后收盘 {close_text}）。这是条件确认，不保证成交或后续走势。")
    elif confirmed == "breakout":
        print(f"🟢 已收盘确认突破 {sym}：最近 {profile['confirmed_closes']} 根 {confirm_bar} K 收在阻力{resistance}上方（最后收盘 {close_text}）。这是条件确认，不保证成交或后续走势。")
    elif live_state == "breakdown":
        print(f"⚠️ 下破预警 {sym} {last} ≤ 支撑{support}，但最近已收盘 {confirm_bar} K 未满足 {profile['confirmed_closes']} 根确认（最后收盘 {close_text}）。")
    elif live_state == "breakout":
        print(f"⚠️ 上破预警 {sym} {last} ≥ 阻力{resistance}，但最近已收盘 {confirm_bar} K 未满足 {profile['confirmed_closes']} 根确认（最后收盘 {close_text}）。")
    else:
        pos = (last - support) / (resistance - support) * 100
        print(f"⚪区间内 {sym} {last}（支撑{support}~阻力{resistance}, 位置{pos:.0f}%）；最后已收盘 {confirm_bar} K {close_text}，未确认突破/破位。")
    if errs:
        print("数据提示：" + "; ".join(errs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
