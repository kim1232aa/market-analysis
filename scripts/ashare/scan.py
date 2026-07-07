#!/usr/bin/env python3
"""
scan.py — A股全市场扫描: 主力资金流排行 × 今日龙虎榜, 交叉发掘强势股(实时真实数据)

用法: python3 scan.py [N]        # N=每榜条数, 默认15
数据源(公开·无需key): 东财 push2/clist(主力净流入排行) + datacenter(今日龙虎榜全表)
产出: ①主力资金流TOP(标注是否上龙虎榜/机构or游资) ②今日龙虎榜涨幅榜 ③⭐强势精选(资金流TOP∩龙虎榜机构买入)
深入某只用 analyze.py <代码>。非投资建议·涨停/龙虎榜多游资博弈高波动·控仓位。
"""
import sys
import ashare_core as ac

if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
    print(__doc__); sys.exit(0)
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 15
errors = []

def yi(x): return "—" if x is None else f"{x/1e8:+.2f}亿"

# ---------- ① 主力资金流排行 (push2 clist, fid=f62 主力净流入 降序) ----------
FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"   # 沪深A股(含科创/创业)
d, e = ac.get(f"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz={N}&po=1&fid=f62"
              f"&fs={FS}&fields=f12,f14,f2,f3,f62,f184")
flow = []
diff = (((d or {}).get("data") or {}).get("diff"))
if e or not diff:
    errors.append(f"资金流排行: {e or '空(或被限流)'}")
else:
    for x in (diff.values() if isinstance(diff, dict) else diff):
        flow.append({"code": x.get("f12"), "name": x.get("f14"),
                     "price": (ac.num(x.get("f2")) or 0)/100, "chg": (ac.num(x.get("f3")) or 0)/100,
                     "main": ac.num(x.get("f62")), "ratio": (ac.num(x.get("f184")) or 0)/100})

# ---------- ② 今日龙虎榜全表 (datacenter) ----------
d2, e2 = ac.get("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
                "&columns=SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLANATION,EXPLAIN,CHANGE_RATE,TURNOVERRATE,BILLBOARD_NET_AMT"
                "&source=DataCenter&sortColumns=TRADE_DATE,BILLBOARD_NET_AMT&sortTypes=-1,-1&pageSize=200")
lhb_rows = []
data2 = ((d2 or {}).get("result") or {}).get("data")
if e2 or not data2:
    errors.append(f"龙虎榜: {e2 or '空'}")
else:
    latest = data2[0]["TRADE_DATE"][:10]
    lhb_rows = [r for r in data2 if r["TRADE_DATE"][:10] == latest]

def who_of(detail):
    if "机构买入" in (detail or ""): return "机构买"
    if "机构卖出" in (detail or ""): return "机构卖"
    return "游资"
lhb_map = {}
for r in lhb_rows:
    lhb_map[r["SECURITY_CODE"]] = {"who": who_of(r.get("EXPLAIN")),
                                   "up": "涨幅" in (r.get("EXPLANATION") or ""),
                                   "net": ac.num(r.get("BILLBOARD_NET_AMT"))}

date = lhb_rows[0]["TRADE_DATE"][:10] if lhb_rows else "最新"
print(f"===== A股强势股扫描 · {date} =====\n")

# 排行①
if flow:
    print(f"【① 主力资金流排行 TOP{len(flow)}】(东财 · 主力净流入降序)")
    print("| # | 代码 | 名称 | 现价 | 涨跌% | 主力净流入 | 净占比% | 龙虎榜 |")
    print("|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(flow, 1):
        lb = lhb_map.get(s["code"])
        tag = ("🔥"+lb["who"] if lb["up"] else "⚠️"+lb["who"]) if lb else "-"
        print(f"| {i} | {s['code']} | {s['name']} | {s['price']:.2f} | {s['chg']:+.2f} | {yi(s['main'])} | {s['ratio']:.1f} | {tag} |")
else:
    print("【① 主力资金流排行】暂缺(push2被风控限流,你本机通常可取) → 以②龙虎榜净买额代替资金维度")

# 龙虎榜②(涨幅榜=强势)
up_board = [r for r in lhb_rows if "涨幅" in (r.get("EXPLANATION") or "")]
up_board.sort(key=lambda r: -(ac.num(r.get("BILLBOARD_NET_AMT")) or 0))
print(f"\n【② 今日龙虎榜·涨幅榜 {len(up_board)}只】(机构买入=资金坐实)")
print("| 代码 | 名称 | 涨跌% | 换手% | 净买额 | 机构/游资明细 |")
print("|---|---|---|---|---|---|")
for r in up_board[:N]:
    print(f"| {r['SECURITY_CODE']} | {r['SECURITY_NAME_ABBR']} | {ac.num(r.get('CHANGE_RATE')):+.2f} | "
          f"{ac.num(r.get('TURNOVERRATE')):.1f} | {yi(ac.num(r.get('BILLBOARD_NET_AMT')))} | {r.get('EXPLAIN','')} |")

# ⭐精选: 优先 资金流TOP∩龙虎榜机构买入; 资金流缺时退化为 龙虎榜机构买入榜
print(f"\n⭐强势精选(机构真金白银买入=最硬信号):")
picks = [s for s in flow if lhb_map.get(s["code"], {}).get("up") and lhb_map[s["code"]]["who"] == "机构买"]
if picks:
    for s in picks:
        print(f"  - {s['name']}({s['code']}) 涨{s['chg']:+.2f}% · 主力净流入{yi(s['main'])} · 机构龙虎榜净买{yi(lhb_map[s['code']]['net'])}")
else:
    inst = [r for r in up_board if lhb_map.get(r["SECURITY_CODE"], {}).get("who") == "机构买"]
    if inst:
        for r in inst[:8]:
            print(f"  - {r['SECURITY_NAME_ABBR']}({r['SECURITY_CODE']}) 涨{ac.num(r.get('CHANGE_RATE')):+.2f}% · 换手{ac.num(r.get('TURNOVERRATE')):.1f}% · 机构龙虎榜净买{yi(ac.num(r.get('BILLBOARD_NET_AMT')))}")
    else:
        print("  (今日涨幅榜无机构买入标的; 多为游资/普通席位)")

print(f"\n深入某只: python3 analyze.py <代码>")
print("⚠️ 非投资建议·涨停/龙虎榜多为游资博弈高波动·A股T+1·务必控仓位。数据为快照(盘中实时/盘后收盘)。")
if errors:
    print("\n!!! 部分数据源失败(不编造) !!!")
    for e in errors: print("  -", e)
