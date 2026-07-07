#!/usr/bin/env python3
"""
market-analysis scan — 找标的 (指定域)

用法:
  python3 scan.py ashare [N]               # A股: 全市场龙虎榜×主力资金流找强势股
  python3 scan.py crypto BTC,ETH,SOL 15m   # 加密: watchlist按机械评分排名
  python3 scan.py crypto                    # 加密默认榜单(BTC,ETH,SOL,BNB,XRP,DOGE)

(加密目前是watchlist型, 非全市场发掘; A股是全市场龙虎榜/资金流发掘。)
"""
import sys, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
if not argv or argv[0] in ("-h", "--help", "help"):
    print(__doc__); sys.exit(0)

dom = argv[0].lower()
if dom in ("ashare", "a", "stock", "astock", "a股", "gu"):
    sub = "ashare"
elif dom in ("crypto", "c", "perp", "coin", "币"):
    sub = "crypto"
else:
    print("请指定域:\n  scan.py ashare [N]\n  scan.py crypto <SYMS> <BAR>"); sys.exit(2)

sys.exit(subprocess.run([sys.executable, "scan.py"] + argv[1:],
                        cwd=os.path.join(HERE, sub)).returncode)
