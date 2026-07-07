#!/usr/bin/env python3
"""
market-analysis — 统一多空分析入口 (自动分流: 加密货币永续 / A股个股)

用法:
  python3 analyze.py ETH 5m      # 加密货币永续 → OKX/Binance/Bybit
  python3 analyze.py BTC 15m
  python3 analyze.py 600519      # A股个股 → 东财/腾讯/新浪
  python3 analyze.py sh600519

自动识别: 参数是"6位数字(可带sh/sz/bj前缀)"=A股; 其余=加密货币。
两域都输出【╔═╗报告块】(必须原样完整输出)。无API key·无依赖(stdlib)。
"""
import sys, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
if not argv or argv[0] in ("-h", "--help", "help"):
    print(__doc__); sys.exit(0)

a = argv[0].lower()
for p in ("sh", "sz", "bj"):
    if a.startswith(p): a = a[2:]; break
is_ashare = a.isdigit() and len(a) == 6            # 6位代码=A股, 否则=加密

sub = "ashare" if is_ashare else "crypto"
sys.exit(subprocess.run([sys.executable, "analyze.py"] + argv,
                        cwd=os.path.join(HERE, sub)).returncode)
