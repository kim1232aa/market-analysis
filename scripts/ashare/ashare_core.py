#!/usr/bin/env python3
"""
ashare_core :: A股(沪深北) 多空分析の共有ライブラリ。
実データ元 = 東方財富(eastmoney) 公開JSON: 実時行情 / K線(日周月/分) / 主力資金流。
API key 不要・依存なし(stdlib urllib)。捏造禁止: 取得失敗は errors[] に記録。
"""
import json, urllib.request, time

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def get(url, tries=4, referer="https://quote.eastmoney.com/"):
    """East money throttles bursts -> retry w/ backoff + browser-ish headers + politeness gap."""
    last = None
    for i in range(tries):
        try:
            time.sleep(0.18)  # politeness gap (avoids RemoteDisconnected on rapid calls)
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA, "Referer": referer,
                "Accept": "application/json, text/plain, */*", "Connection": "close"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8", "ignore")), None
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(0.7 * (i + 1))  # backoff before retry
    return None, last

def get_text(url, encoding="utf-8", tries=3):
    """Raw-text fetch (for Tencent qt.gtimg GBK, non-JSON)."""
    last = None
    for i in range(tries):
        try:
            time.sleep(0.15)
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA, "Referer": "https://gu.qq.com/", "Connection": "close"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode(encoding, "ignore"), None
        except Exception as e:
            last = f"{type(e).__name__}: {e}"; time.sleep(0.5 * (i + 1))
    return None, last

def tencent_sym(code):
    sid, c = secid(code)
    if c[:1] in ("8", "4") or c[:3] == "920": return "bj" + c
    return ("sh" if sid.startswith("1.") else "sz") + c

def num(x):
    try:
        if x in ("-", "", None): return None
        return float(x)
    except: return None
def pct(a, b): return None if not b else (a - b) / b * 100.0

# ---------- 代码 -> 东财 secid (1.=沪 0.=深/北) ----------
def secid(code):
    c = "".join(ch for ch in str(code).lower() if ch.isdigit())
    if c[:1] in ("6", "5", "9") or c[:2] in ("11", "68", "51", "58"):
        return f"1.{c}", c
    return f"0.{c}", c

# ---------- indicators ----------
def ema(vals, p):
    if not vals: return None
    k = 2/(p+1); e = vals[0]
    for v in vals[1:]: e = v*k + e*(1-k)
    return e
def ema_series(vals, p):
    if not vals: return []
    k = 2/(p+1); out = [vals[0]]
    for v in vals[1:]: out.append(v*k + out[-1]*(1-k))
    return out
def ma(closes, n): return sum(closes[-n:])/n if len(closes) >= n else None
def rsi(closes, p=14):
    if len(closes) < p+1: return None
    g = l = 0.0
    for i in range(1, p+1):
        d = closes[i]-closes[i-1]; g += max(d, 0); l += max(-d, 0)
    ag, al = g/p, l/p
    for i in range(p+1, len(closes)):
        d = closes[i]-closes[i-1]
        ag = (ag*(p-1)+max(d, 0))/p; al = (al*(p-1)+max(-d, 0))/p
    return 100.0 if al == 0 else 100 - 100/(1+ag/al)
def atr(highs, lows, closes, p=14):
    n = len(closes)
    if n < p+1: return None
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, n)]
    a = sum(trs[:p])/p
    for i in range(p, len(trs)): a = (a*(p-1)+trs[i])/p
    return a
def macd(closes):
    if len(closes) < 27: return None
    e12, e26 = ema_series(closes, 12), ema_series(closes, 26)
    dif = [a-b for a, b in zip(e12, e26)]
    dea = ema_series(dif, 9)
    cross = ("金叉" if dif[-1] > dea[-1] and dif[-2] <= dea[-2]
             else "死叉" if dif[-1] < dea[-1] and dif[-2] >= dea[-2]
             else "多头" if dif[-1] > dea[-1] else "空头")
    return {"dif": dif[-1], "dea": dea[-1], "bar": 2*(dif[-1]-dea[-1]), "cross": cross}
def boll(closes, n=20, k=2):
    if len(closes) < n: return None
    w = closes[-n:]; mid = sum(w)/n
    sd = (sum((x-mid)**2 for x in w)/n) ** 0.5
    up, low = mid+k*sd, mid-k*sd
    return {"mid": mid, "up": up, "low": low, "pos": (closes[-1]-low)/(up-low) if up > low else 0.5}
def wtrend(series):
    s = [x for x in series if x is not None]
    if len(s) < 2: return 0
    d = s[-1]-s[0]; base = abs(s[0]) or 1
    return 1 if d/base > 0.0005 else -1 if d/base < -0.0005 else 0

# ---------- 东财 fetchers ----------
# ---- 实时行情: 东财优先, 腾讯回退 ----
def _em_realtime(code):
    sid, _ = secid(code)
    d, e = get(f"https://push2.eastmoney.com/api/qt/stock/get?secid={sid}"
               "&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f162,f167,f168,f169,f170")
    if e: return None, e
    x = (d or {}).get("data")
    if not x: return None, "空(代码或休市?)"
    def v(k, div=100):
        n = num(x.get(k)); return n/div if n is not None else None
    return {"code": x.get("f57"), "name": x.get("f58"), "source": "东财",
            "price": v("f43"), "high": v("f44"), "low": v("f45"), "open": v("f46"), "prevclose": v("f60"),
            "vol": num(x.get("f47")), "amount": num(x.get("f48")),
            "vol_ratio": v("f50"), "up_limit": v("f51"), "down_limit": v("f52"),
            "pe": v("f162"), "pb": v("f167"), "turnover": v("f168"),
            "chg": v("f169"), "chg_pct": v("f170")}, None
def _tc_realtime(code):
    txt, e = get_text(f"https://qt.gtimg.cn/q={tencent_sym(code)}", "gbk")
    if e or not txt or '"' not in txt: return None
    try:
        f = txt.split('"')[1].split("~")   # 索引经实值核对确定
        if len(f) < 50: return None
        return {"code": f[2], "name": f[1], "source": "腾讯", "price": num(f[3]),
                "high": num(f[33]), "low": num(f[34]), "open": num(f[5]), "prevclose": num(f[4]),
                "vol": num(f[6]), "amount": (num(f[37]) or 0)*10000,
                "vol_ratio": num(f[49]), "up_limit": num(f[47]), "down_limit": num(f[48]),
                "pe": num(f[52]), "pb": num(f[46]), "turnover": num(f[38]),
                "chg": num(f[31]), "chg_pct": num(f[32])}
    except Exception: return None
def realtime(code, errors):
    d, e = _em_realtime(code)
    if d: return d
    t = _tc_realtime(code)
    if t: errors.append(f"行情源: 东财不可用({e})→已切腾讯"); return t
    errors.append(f"实时行情: 东财+腾讯均失败({e})"); return None

# ---- K线: 东财优先, 腾讯回退(日/周/月) ----
def _em_kline(code, klt, lmt):
    sid, _ = secid(code)
    d, e = get(f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={sid}"
               f"&klt={klt}&fqt=1&lmt={lmt}&end=20500101&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57,f61")
    if e: return None, e
    rows = ((d or {}).get("data") or {}).get("klines")
    if not rows: return None, "空"
    o, c, h, l, vol, amt, tov = [], [], [], [], [], [], []
    for r in rows:
        p = r.split(",")           # date,open,close,high,low,vol,amount,turnover
        o.append(num(p[1])); c.append(num(p[2])); h.append(num(p[3])); l.append(num(p[4]))
        vol.append(num(p[5])); amt.append(num(p[6])); tov.append(num(p[7]) if len(p) > 7 else None)
    return {"date": [r.split(",")[0] for r in rows], "open": o, "close": c, "source": "东财",
            "high": h, "low": l, "vol": vol, "amount": amt, "turnover": tov}, None
def _tc_kline(code, klt, lmt):
    period = {101: "day", 102: "week", 103: "month"}.get(klt)
    if not period: return None            # 分钟线仅东财
    sym = tencent_sym(code)
    d, e = get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},{period},,,{lmt},qfq")
    if e: return None
    node = ((d or {}).get("data") or {}).get(sym) or {}
    arr = None
    for key in ("qfq"+period, period, "qfqday", "day"):
        if isinstance(node.get(key), list) and node[key]: arr = node[key]; break
    if arr is None:
        for vv in node.values():
            if isinstance(vv, list) and vv and isinstance(vv[0], list): arr = vv; break
    if not arr: return None
    o, c, h, l, vol = [], [], [], [], []   # [date,open,close,high,low,volume,...]
    for r in arr:
        o.append(num(r[1])); c.append(num(r[2])); h.append(num(r[3])); l.append(num(r[4]))
        vol.append(num(r[5]) if len(r) > 5 else None)
    return {"date": [r[0] for r in arr], "open": o, "close": c, "high": h, "low": l,
            "vol": vol, "amount": [None]*len(c), "turnover": [None]*len(c), "source": "腾讯"}
def _sina_kline(code, klt, lmt):
    scale = {101: 240, 60: 60, 30: 30, 15: 15, 5: 5}.get(klt)   # 周/月 新浪不支持
    if not scale: return None
    d, e = get(f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               f"CN_MarketData.getKLineData?symbol={tencent_sym(code)}&scale={scale}&ma=no&datalen={lmt}",
               referer="https://finance.sina.com.cn")
    if e or not isinstance(d, list) or not d: return None
    o, c, h, l, vol = [], [], [], [], []
    for r in d:                                   # 新浪已是 旧→新
        o.append(num(r.get("open"))); c.append(num(r.get("close")))
        h.append(num(r.get("high"))); l.append(num(r.get("low"))); vol.append(num(r.get("volume")))
    return {"date": [r.get("day") for r in d], "open": o, "close": c, "high": h, "low": l,
            "vol": vol, "amount": [None]*len(c), "turnover": [None]*len(c), "source": "新浪"}
def kline(code, klt, lmt, errors):
    d, e = _em_kline(code, klt, lmt)
    if d: return d
    t = _tc_kline(code, klt, lmt)
    if t: errors.append(f"K线{klt}: 东财不可用→腾讯"); return t
    s = _sina_kline(code, klt, lmt)
    if s: errors.append(f"K线{klt}: 东财/腾讯不可用→新浪"); return s
    errors.append(f"K线{klt}: {e}"); return None

def _em_fflow(code, lmt):
    """东财主力资金流(日). 每行 date,主力,小单,中单,大单,超大单 (净流入元)."""
    sid, _ = secid(code)
    d, e = get(f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid={sid}"
               f"&lmt={lmt}&klt=101&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56")
    if e: return None
    rows = ((d or {}).get("data") or {}).get("klines")
    if not rows: return None
    out = []
    for r in rows:
        p = r.split(",")
        out.append({"date": p[0], "main": num(p[1]), "small": num(p[2]),
                    "mid": num(p[3]), "big": num(p[4]), "xbig": num(p[5]), "source": "东财"})
    return out
def _sina_fflow(code, lmt):
    """新浪资金流(口径不同): netamount=主力净流入, r0_net=超大单净流入."""
    d, e = get(f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               f"MoneyFlow.ssl_qsfx_zjlrqs?daima={tencent_sym(code)}&num={lmt}&sort=opendate&asc=0",
               referer="https://finance.sina.com.cn")
    if e or not isinstance(d, list) or not d: return None
    out = []
    for r in reversed(d):                          # 新浪 新→旧, 反转成 旧→新
        out.append({"date": (r.get("opendate") or "")[:10], "main": num(r.get("netamount")),
                    "xbig": num(r.get("r0_net")), "big": None, "mid": None, "small": None,
                    "source": "新浪"})
    return out
def fflow(code, lmt, errors):
    d = _em_fflow(code, lmt)
    if d: return d
    s = _sina_fflow(code, lmt)
    if s: errors.append("主力资金流: 东财不可用→新浪(口径不同)"); return s
    errors.append("主力资金流: 东财+新浪均失败"); return None

def lhb(code, errors):
    """龙虎榜(东财datacenter-web, 与push2不同源常可用). 返回最近一次上榜信息."""
    _, c = secid(code)
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
           "&columns=SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLANATION,EXPLAIN,CHANGE_RATE,"
           "BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT&source=DataCenter"
           f"&sortColumns=TRADE_DATE&sortTypes=-1&pageSize=3&filter=(SECURITY_CODE=%22{c}%22)")
    d, e = get(url)
    if e: errors.append(f"龙虎榜: {e}"); return None
    rows = ((d or {}).get("result") or {}).get("data")
    if not rows: return {"on_list": False}
    r = rows[0]
    return {"on_list": True, "date": (r.get("TRADE_DATE") or "")[:10],
            "reason": r.get("EXPLANATION"), "detail": r.get("EXPLAIN"),
            "net_amt": num(r.get("BILLBOARD_NET_AMT")), "buy": num(r.get("BILLBOARD_BUY_AMT")),
            "sell": num(r.get("BILLBOARD_SELL_AMT")), "change_rate": num(r.get("CHANGE_RATE"))}

def build_tech(kd):
    """日K dict -> 技术指标. """
    if not kd: return None
    c, h, l = kd["close"], kd["high"], kd["low"]; n = len(c)
    return {"n": n, "ma5": ma(c, 5), "ma10": ma(c, 10), "ma20": ma(c, 20), "ma60": ma(c, 60),
            "rsi14": rsi(c), "atr14": atr(h, l, c), "macd": macd(c), "boll": boll(c),
            "swing_high_20": max(h[-20:]) if n >= 5 else None,
            "swing_low_20": min(l[-20:]) if n >= 5 else None,
            "swing_high_60": max(h[-60:]) if n >= 20 else None,
            "swing_low_60": min(l[-60:]) if n >= 20 else None,
            "close": c[-1], "recent_close": [round(x, 2) for x in c[-10:]]}

# ---------- 信号打标 ----------
def _t_limit(rt):
    p, up, dn = rt.get("price"), rt.get("up_limit"), rt.get("down_limit")
    if None in (p, up, dn) or p <= 0: return ("—", 0)
    du, dd = (up-p)/p*100, (p-dn)/p*100
    if p >= up*0.999:  return ("封涨停·极强(次日博弈)", 1.5)
    if du < 2:         return (f"逼近涨停(距{du:.1f}%)·强", 1.2)
    if p <= dn*1.001:  return ("封跌停·极弱", -1.5)
    if dd < 2:         return (f"逼近跌停(距{dd:.1f}%)·弱", -1.2)
    return (f"距涨停{du:.1f}%/跌停{dd:.1f}%·中性区", 0)
def _t_mainflow(today, amount):
    if today is None or not amount: return ("—", 0)
    r = today/amount
    if r > 0.10:  return (f"主力大幅净流入({today/1e8:+.2f}亿)", 1.5)
    if r > 0.03:  return (f"主力净流入({today/1e8:+.2f}亿)", 0.8)
    if r < -0.10: return (f"主力大幅净流出({today/1e8:+.2f}亿)", -1.5)
    if r < -0.03: return (f"主力净流出({today/1e8:+.2f}亿)", -0.8)
    return (f"主力资金基本平衡({today/1e8:+.2f}亿)", 0)
def _t_mainflow5(rows):
    if not rows: return ("—", 0)
    cum = sum(x["main"] for x in rows[-5:] if x["main"] is not None)
    tr = wtrend([x["main"] for x in rows[-5:]])
    tag = "近5日累计" + ("净流入" if cum > 0 else "净流出") + f"{cum/1e8:+.2f}亿"
    return (tag + ("·增势" if tr > 0 else "·减势" if tr < 0 else ""),
            0.7 if cum > 0 else -0.7 if cum < 0 else 0)
def _t_volprice(chg_pct, vol_ratio):
    if chg_pct is None or vol_ratio is None: return ("—", 0)
    up = chg_pct > 0
    if vol_ratio > 1.2:
        return ("量价齐升·健康", 1.2) if up else ("放量下跌·出货嫌疑", -1.2)
    if vol_ratio < 0.8:
        return ("缩量上涨·上攻乏力", 0.3) if up else ("缩量回调·抛压不重", -0.2)
    return ("量能平稳", 0.2 if up else -0.2)
def _t_ma(t, price):
    m5, m10, m20, m60 = t.get("ma5"), t.get("ma10"), t.get("ma20"), t.get("ma60")
    if None in (m5, m10, m20): return ("—", 0)
    if m5 > m10 > m20 and (m60 is None or m20 > m60): return ("均线多头排列", 1.2)
    if m5 < m10 < m20 and (m60 is None or m20 < m60): return ("均线空头排列", -1.2)
    return ("均线纠缠·震荡", 0)
def _t_macd(m):
    if not m: return ("—", 0)
    c = m["cross"]; wl = "水上" if m["dif"] > 0 else "水下"
    return {"金叉": (f"MACD金叉({wl})", 1.0), "死叉": (f"MACD死叉({wl})", -1.0),
            "多头": (f"MACD多头({wl})", 0.5), "空头": (f"MACD空头({wl})", -0.5)}[c]
def _t_rsi(t):
    r = t.get("rsi14")
    if r is None: return ("—", 0)
    if r >= 70: return (f"RSI{r:.0f} 超买", -0.5)
    if r >= 55: return (f"RSI{r:.0f} 偏强", 0.5)
    if r > 45:  return (f"RSI{r:.0f} 中性", 0)
    if r > 30:  return (f"RSI{r:.0f} 偏弱", -0.5)
    return (f"RSI{r:.0f} 超卖", 1)
def _t_turnover(tv):
    if tv is None: return ("—", 0)
    if tv > 15: return (f"换手{tv:.1f}%·过热(游资博弈)", -0.3)
    if tv >= 3: return (f"换手{tv:.1f}%·活跃", 0.3)
    if tv < 1:  return (f"换手{tv:.1f}%·清淡", -0.2)
    return (f"换手{tv:.1f}%·温和", 0)
def _t_boll(t):
    b = t.get("boll")
    if not b: return ("—", 0)
    p = b["pos"]
    if p > 0.9: return ("触BOLL上轨·超买", -0.3)
    if p < 0.1: return ("触BOLL下轨·超卖", 0.5)
    return (f"BOLL中位({p*100:.0f}%)", 0)

def _fmt(x, nd=2):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))
def bias_emoji(s):
    if s >= 1:  return "偏多✅"
    if s > 0:   return "偏多"
    if s <= -1: return "偏空🔻"
    if s < 0:   return "偏空⚠️"
    return "中性➖"

def _t_lhb(info):
    # EXPLAIN is the exchange's own seat-type description, not an independently
    # verified investor-identity feed -- a "机构" substring match is real text
    # from the source, but treating it as a confirmed institutional identity
    # (and scoring it higher than a plain net-buy) overclaims what we fetched.
    # Keep the raw fact visible; score net-buy/sell direction only.
    if not info or not info.get("on_list"): return None
    net, detail = info.get("net_amt"), info.get("detail") or ""
    seat_note = "说明含机构字样(未核验身份)" if "机构" in detail else "席位属性未核验"
    if net and net > 0: return (f"龙虎榜净买{net/1e8:+.2f}亿·{seat_note}", 0.8)
    if net and net < 0: return (f"龙虎榜净卖{net/1e8:+.2f}亿·{seat_note}", -0.8)
    return (f"龙虎榜上榜·{seat_note}", 0)

def signal_rows(rt, tech, ff_today, ff5, lhb=None, lhb_today=False):
    amount = rt.get("amount")
    rows = [
        ("涨跌停状态", _fmt_price(rt.get("price")), *_t_limit(rt)),
        ("主力资金(今)", (f"{ff_today/1e8:+.2f}亿" if ff_today is not None else "—需东财"), *_t_mainflow(ff_today, amount)),
        ("主力资金(5日)", "", *_t_mainflow5(ff5)),
        ("量价", f"量比{_fmt(rt.get('vol_ratio'))}", *_t_volprice(rt.get("chg_pct"), rt.get("vol_ratio"))),
        ("均线排列", f"MA20 {_fmt(tech.get('ma20'))}", *_t_ma(tech, rt.get("price"))),
        ("MACD", "", *_t_macd(tech.get("macd"))),
        ("RSI14", _fmt(tech.get("rsi14"), 0), *_t_rsi(tech)),
        ("换手率", f"{_fmt(rt.get('turnover'))}%", *_t_turnover(rt.get("turnover"))),
        ("BOLL位置", "", *_t_boll(tech)),
    ]
    if lhb_today:
        t = _t_lhb(lhb)
        if t: rows.append(("龙虎榜", f"{(lhb.get('net_amt') or 0)/1e8:+.2f}亿", *t))
    total = sum(r[3] for r in rows)
    if total >= 3:    bias = "偏多"
    elif total >= 1:  bias = "中性偏多"
    elif total > -1:  bias = "中性/震荡"
    elif total > -3:  bias = "中性偏空"
    else:             bias = "偏空"
    return rows, round(total, 2), bias
def _fmt_price(p): return "—" if p is None else f"{p:.2f}"

# ---------- output policy (pure helpers; no network) ----------
# Confirmation/risk-presentation profiles, mirroring scripts/crypto/perp_core.py.
# They only change how much confirmation is asked for in candidate scenarios;
# they never turn a partial data set into a trading instruction.
PROFILES = {
    "conservative": {"label": "保守", "confirmed_closes": 2,
                      "note": "仍需日线收盘确认，并检查多周期方向与止损距离后再考虑"},
    "balanced":     {"label": "均衡", "confirmed_closes": 1,
                      "note": "回踩或突破均可列入候选，先确认触发与可承受止损"},
    "active":       {"label": "积极", "confirmed_closes": 1,
                      "note": "可更早跟踪候选情景，但仍以明确触发和止损为前提，不追封板"},
}

def profile_config(name):
    key = (name or "balanced").lower()
    if key not in PROFILES:
        raise ValueError(f"unknown profile {name!r}; choose one of {', '.join(PROFILES)}")
    return {"name": key, **PROFILES[key]}

def assess_data_quality(rt, tech, mtf, ff, errors=None, lhb=None):
    """Grade whether there is enough live evidence for a directional call.

    `dir=None` in an mtf leg means that timeframe's data/indicator history is
    unavailable -- deliberately different from `dir=0` (usable but neutral). A
    missing price/日K/任一多周期腿/主力资金流 produces status="NO_TRADE": the
    report block still shows whatever numbers ARE available, but 建议(主策略)
    must not manufacture a directional call out of a partial picture.
    """
    core_missing = []
    if not rt or rt.get("price") is None:
        core_missing.append("东财/腾讯实时行情")
    if not tech or tech.get("rsi14") is None:
        core_missing.append("日K技术指标(需≥15根)")
    missing_tfs = [label for label, direction, _ in (mtf or []) if direction is None]
    core_missing.extend(f"{label}周期" for label in missing_tfs)
    if ff is None:
        core_missing.append("主力资金流(东财)")

    optional_missing = []
    if lhb is None:
        optional_missing.append("龙虎榜")

    status = "NO_TRADE" if core_missing else ("CAUTION" if optional_missing else "READY")
    return {"status": status, "core_missing": core_missing, "optional_missing": optional_missing,
            "error_count": len(errors or []), "missing_timeframes": missing_tfs}
