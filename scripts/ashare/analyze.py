#!/usr/bin/env python3
"""
ashare-analysis / analyze.py — A股(沪深北)个股多空分析(实时真实数据·东方财富公开接口)

用法: python3 analyze.py [代码]
  代码: 600519 / sh600519 / 000001 / 300750 (默认 600519 贵州茅台)
环境: HTTPS_PROXY=http://<代理>:<端口> (被墙时前缀)

输出【报告块】(必须原样完整输出): 快照 / 多周期共振(60分·日·周·月) / 机械评分+基调 /
  技术&资金面板 / 主力资金流明细(超大/大/中/小单) / 关键位 / 情景剧本(T+1·涨跌停) / 合并结论·建议
数据源(公开·无需key): 东方财富 push2/push2his。无依赖(stdlib)。
铁律: 只输出脚本给的数字, 失败源写errors不编造; A股T+1&涨跌停; 非投资建议·控仓位。
"""
import sys, json
import ashare_core as ac

if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
    print(__doc__); sys.exit(0)
CODE = sys.argv[1] if len(sys.argv) > 1 else "600519"

errors = []
rt   = ac.realtime(CODE, errors)
kd   = ac.kline(CODE, 101, 120, errors)     # 日线120根(够MA60+指标)
tech = ac.build_tech(kd)
ff   = ac.fflow(CODE, 6, errors)            # 主力资金流 近6日
ff_today = ff[-1]["main"] if ff else None
lhb  = ac.lhb(CODE, errors)                 # 龙虎榜(东财datacenter)
_recent = {d[:10] for d in (kd["date"][-20:] if kd else [])}
lhb_today = bool(lhb and lhb.get("on_list") and kd and lhb.get("date", "")[:10] == kd["date"][-1][:10])
lhb_recent = bool(lhb and lhb.get("on_list") and lhb.get("date", "")[:10] in _recent)  # 近20交易日内才算有效

# 多周期共振
LADDER = [("60分", 60), ("日", 101), ("周", 102), ("月", 103)]
mtf = []
for label, klt in LADDER:
    k = kd if klt == 101 else ac.kline(CODE, klt, 60, errors)   # 日线复用kd,减少请求
    if not k: mtf.append((label, None, None)); continue
    c = k["close"]; m5, m20 = ac.ma(c, 5), ac.ma(c, 20); r = ac.rsi(c)
    d = 1 if (m5 and m20 and c[-1] > m5 > m20) else -1 if (m5 and m20 and c[-1] < m5 < m20) else 0
    mtf.append((label, d, r))
dirs = [d for _, d, _ in mtf if d is not None]
rs = sum(dirs)
if dirs and all(d > 0 for d in dirs):   reson = "🟢多头共振(各周期同向向上·高信心)"
elif dirs and all(d < 0 for d in dirs): reson = "🔴空头共振(各周期同向向下·高信心)"
elif rs > 0:  reson = "偏多但未完全共振(存在分歧)"
elif rs < 0:  reson = "偏空但未完全共振(存在分歧)"
else:         reson = "多周期分歧·区间/转折(低信心,轻仓)"

if not rt or not tech:
    print("！！数据获取失败(不要编造)：", "; ".join(errors)); sys.exit(1)
rows, total, bias = ac.signal_rows(rt, tech, ff_today, ff, lhb, lhb_today)

g = ac._fmt
def q(x): return "—" if x is None else f"{x:.2f}"
def dtxt(d): return "↑多" if d == 1 else "↓空" if d == -1 else "→震荡" if d == 0 else "—"
amp = (rt["high"]-rt["low"])/rt["prevclose"]*100 if rt.get("prevclose") else None

print(f"===== {rt['name']}({rt['code']}) · A股 · DATA REPORT =====")
print(f"现价 {q(rt['price'])} | 涨跌 {g(rt['chg_pct'])}% | 换手 {g(rt['turnover'])}% | 量比 {g(rt['vol_ratio'])} "
      f"| PE {g(rt['pe'])} PB {g(rt['pb'])} | 成交额 {(rt['amount'] or 0)/1e8:.1f}亿")

print("\n╔═══════ 报告块 · 必须原样完整输出 (禁止改写成散文 / 禁止删表删行) ═══════╗")
print(f"**{rt['name']}({rt['code']}) · A股 · 实时快照**  现价 {q(rt['price'])} | {g(rt['chg_pct'])}% "
      f"| 振幅 {g(amp)}% | 换手 {g(rt['turnover'])}% | 量比 {g(rt['vol_ratio'])} | PE {g(rt['pe'])} PB {g(rt['pb'])} "
      f"| 成交额 {(rt['amount'] or 0)/1e8:.1f}亿 | 涨停 {q(rt['up_limit'])} 跌停 {q(rt['down_limit'])}")

print(f"\n**多周期共振：{reson}**")
print("| 周期 | 方向 | RSI |")
print("|---|---|---|")
for lab, d, r in mtf:
    print(f"| {lab} | {dtxt(d)} | {g(r,0)} |")

print(f"\n**机械评分 {total} → 基调:{bias}**（≥3偏多/1~3偏多/±1震荡/≤-1偏空；量化参考,结合共振与结构）\n")
print("| 指标 | 数值 | 解读 | 倾向 |")
print("|---|---|---|---|")
for name, val, desc, sc in rows:
    print(f"| {name} | {val} | {desc} | {ac.bias_emoji(sc)} |")

# 主力资金流明细
if ff:
    t = ff[-1]
    def yi(x): return "—" if x is None else f"{x/1e8:+.2f}亿"
    print(f"\n**主力资金流(今日·源{t.get('source','?')})**  超大单 {yi(t['xbig'])} ｜ 大单 {yi(t['big'])} ｜ 中单 {yi(t['mid'])} ｜ 小单 {yi(t['small'])}"
          f"  → 主力净流入 {yi(t['main'])}")
# 龙虎榜 (仅近20交易日内有效; 更早的忽略)
if lhb_recent:
    tag = "今日上榜🔥" if lhb_today else f"近期上榜({lhb['date']})"
    net = lhb.get("net_amt") or 0
    print(f"**龙虎榜·{tag}**  {lhb.get('reason','')} ｜ {lhb.get('detail','')} ｜ 净买 {net/1e8:+.2f}亿(当日{g(lhb.get('change_rate'))}%)")

# 关键位 + 情景剧本 (regime-aware: 以现价把各价位分为压力/支撑)
ma5, ma10, ma20, ma60 = tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("ma60")
sh20, sl20 = tech.get("swing_high_20"), tech.get("swing_low_20")
sh60, sl60 = tech.get("swing_high_60"), tech.get("swing_low_60")
atrv = tech.get("atr14") or (rt["price"]*0.02)
p = rt["price"]; u = 1.2*atrv
def rr(rw, rk): return f"1:{rw/rk:.1f}" if rk and rk > 0 else "—"
cand = [("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60),
        ("近20高", sh20), ("近20低", sl20), ("前高", sh60), ("前低", sl60)]
cand = [(n, v) for n, v in cand if v]
above = sorted([(n, v) for n, v in cand if v > p*1.002], key=lambda x: x[1])
below = sorted([(n, v) for n, v in cand if v < p*0.998], key=lambda x: -x[1])
res1n, res1 = above[0] if above else ("涨停", rt["up_limit"])
res2n, res2 = above[1] if len(above) > 1 else ("涨停", rt["up_limit"])
sup1n, sup1 = below[0] if below else ("跌停", rt["down_limit"])
sup2n, sup2 = below[1] if len(below) > 1 else ("跌停", rt["down_limit"])
ma20_rel = "上方(偏多)" if (ma20 and p >= ma20) else "下方(偏空)" if ma20 else "?"
print(f"\n**关键位**  压力 {q(res1)}({res1n})/{q(res2)}({res2n}) ｜ 现价 {q(p)}·在MA20{ma20_rel} ｜ 支撑 {q(sup1)}({sup1n})/{q(sup2)}({sup2n}) ｜ 涨停 {q(rt['up_limit'])} 跌停 {q(rt['down_limit'])} ｜ ATR {q(atrv)}")
print("\n| 情景 | 触发 | 进场 | 止损 | 目标 | R:R |")
print("|---|---|---|---|---|---|")
print(f"| 🟢回踩低吸 | 回踩{q(sup1)}({sup1n})缩量企稳 | {q(sup1)} | {q(sup1-u)} | {q(res1)}→{q(res2)} | {rr(res1-sup1, u)} |")
btgt = res1 + max(res2 - res1, 2*u)   # 目标至少一个测量位,避免res1≈res2时目标=进场
print(f"| 🟢放量突破 | 放量站上{q(res1)}({res1n}) | {q(res1)} | {q(res1-u)} | {q(btgt)} | {rr(btgt-res1, u)} |")
print(f"| 🔴跌破止损 | 收盘跌破{q(sup1)}({sup1n}) | {q(sup1)} | — | {q(sup2)}({sup2n}) | 离场/反手 |")
if ma20 and p < ma20*0.998:
    print(f"| 🔴反弹减仓 | 反弹到{q(ma20)}(MA20压制) | {q(ma20)} | {q(ma20+u)} | {q(sup1)} | 空头趋势·逢高减 |")
elif rt["price"] >= rt["up_limit"]*0.999:
    print(f"| ⚠️封板博弈 | 封涨停{q(rt['up_limit'])} | 次日集合竞价 | 高风险 | — | 打板/隔日冲高 |")
print(f"\n**总开关 {q(ma20)}(MA20生命线)**：站上=偏多可持/低吸；跌破=转弱,反弹即减。")

# 合并结论 & 建议 (确定性)
def drivers(pos, k=2):
    pool = [r for r in rows if (r[3] > 0) == pos and r[3] != 0]
    pool.sort(key=lambda r: -abs(r[3])); return pool[:k]
bull, bear = drivers(True), drivers(False)
above20 = bool(ma20 and p >= ma20)
print(f"\n**合并结论：{bias}**", end="")
if bull: print(" ｜ 多方：" + "；".join(f"{n}({d})" for n, _, d, _ in bull), end="")
if bear: print(" ｜ 空方/风险：" + "；".join(f"{n}({d})" for n, _, d, _ in bear), end="")
print()
if bias in ("偏多", "中性偏多"):
    rec = (f"🟢持股/回踩{q(sup1)}({sup1n})低吸，止损{q(sup1-u)}，目标{q(res1)}→{q(res2)}" if above20
           else f"🟢现价在MA20下方,先等站上{q(ma20)}(MA20)转强再进,当前宜轻仓/观望")
elif bias in ("偏空", "中性偏空"):
    rec = f"🔴反弹到{q(res1)}({res1n})减仓，跌破{q(sup1)}({sup1n})止损，勿抄底"
else:
    rec = f"➖区间震荡：{q(sup1)}({sup1n})~{q(res1)}({res1n})高抛低吸，站稳MA20偏多、下方偏空"
print(f"- **建议(主策略)**：{rec}")
if ff_today is not None and rt.get("amount"):
    if ff_today/rt["amount"] > 0.03:
        print(f"- **资金面**：主力今日净流入{ff_today/1e8:+.2f}亿，回调是上车机会，跟资金做多")
    elif ff_today/rt["amount"] < -0.03:
        print(f"- **资金面**：主力今日净流出{ff_today/1e8:+.2f}亿，反弹是减仓机会，别接飞刀")
print(f"- **T+1提醒**：当日买入次日才可卖，隔夜有跳空风险；涨停封板买不进、跌停封板卖不出。")

ffsrc = ff[-1].get("source") if ff else "缺"
lhbsrc = ("今日上榜" if lhb_today else "近期上榜") if lhb_recent else ("近期无" if lhb else "缺")
src = f"数据源: 行情={rt.get('source','?')}·K线={(kd or {}).get('source','?')}·资金流={ffsrc}·龙虎榜={lhbsrc}"
if ff is None: src += " ｜ ⚠️资金流暂缺"
print(f"\n{src}")
print("⚠️ 非投资建议·A股T+1&涨跌停板·务必控制仓位。数据为最新快照(盘中实时/盘后为当日收盘)。位与R:R为结构自动测算,需按盘微调。")
print("╚═══ 报告块结束 · 须完整输出(面板表/主力资金流/合并结论/建议不可删),并附下方 ----- JSON ----- 锚点为证:无JSON=未跑脚本=假报告 ═══╝")

if errors:
    print("\n!!! 部分数据源失败(不要编造,如实告知) !!!")
    for e in errors: print("  -", e)
OUT = {"code": rt["code"], "name": rt["name"], "realtime": rt, "tech": tech,
       "fflow_today": ff[-1] if ff else None, "mtf": [{"tf": l, "dir": d, "rsi": r} for l, d, r in mtf],
       "resonance": reson, "bias_score": total, "bias": bias, "errors": errors}
print("\n----- JSON -----")
print(json.dumps(OUT, ensure_ascii=False, separators=(",", ":")))
