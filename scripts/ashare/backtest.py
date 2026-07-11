#!/usr/bin/env python3
"""backtest.py :: replay a price-only A股 long strategy from a local OHLC decision log.

This is an execution-layer experiment, NOT a claim that the live signal panel
(analyze.py/scan.py) has alpha, and NOT a substitute for it. It only replays
decisions that were already recorded at a bar's close: entries fill no earlier
than the NEXT bar's open (never the decision bar itself), and it applies a
one-bar minimum holding period to approximate A股 T+1 (buy today, earliest
sell is two bars after the decision bar = one full day after entry). It CANNOT
model a locked 涨跌停 perfectly -- such exits are counted as blocked, not filled.

Input: CSV, JSON, or JSONL with OHLC columns (open/high/low/close, timestamp
optional) plus optional side (long only; short/sell inputs are ignored --
A股无法裸做空), signal_score, atr, stop, target, funding_rate,
up_limit, down_limit (涨停/跌停价，用于识别锁死无法卖出的情形).

Usage:
    python3 backtest.py decisions.csv
    python3 backtest.py decisions.json --profile conservative

Profiles gate the minimum recorded |signal_score| to take a trade:
  conservative=3, balanced=1, active=0.25 (matches analyze.py's 机械评分 scale).
Does NOT model 停牌、涨跌停无法买入、真实成交量约束 -- do not infer those from
this script's output.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROFILE_MIN_SCORE = {"conservative": 3.0, "balanced": 1.0, "active": 0.25}


def fnum(value, default=None):
    try:
        if value in (None, "", "-", "—"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def side_of(value):
    if isinstance(value, (int, float)):
        return 1 if value > 0 else -1 if value < 0 else 0
    text = str(value or "").strip().lower()
    if text in {"long", "buy", "多", "1", "+1"}:
        return 1
    if text in {"short", "sell", "空", "-1"}:
        return -1
    return 0


def load_rows(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(raw.splitlines()))
    elif path.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        parsed = json.loads(raw)
        rows = parsed.get("bars", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(rows, list):
        raise ValueError("输入必须是 OHLC 行数组，或包含 bars 数组的 JSON 对象")
    out = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        bar = {key: fnum(row.get(key)) for key in
               ("open", "high", "low", "close", "atr", "stop", "target", "funding_rate",
                "up_limit", "down_limit", "signal_score")}
        if any(bar[key] is None or bar[key] <= 0 for key in ("open", "high", "low", "close")):
            raise ValueError(f"第 {index + 1} 行缺少有效 OHLC")
        bar["timestamp"] = str(row.get("timestamp", row.get("time", index)))
        bar["side"] = side_of(row.get("side", row.get("signal")))
        out.append(bar)
    if len(out) < 3:
        raise ValueError("至少需要 3 根有效 K 线")
    return out


def atr_series(rows, period=14):
    """ATR at index i uses only rows[0..i] -- never a future bar."""
    trs, result, previous_close, smooth = [], [], None, None
    for row in rows:
        tr = row["high"] - row["low"] if previous_close is None else max(
            row["high"] - row["low"], abs(row["high"] - previous_close), abs(row["low"] - previous_close))
        trs.append(tr)
        if len(trs) < period:
            result.append(sum(trs) / len(trs))
        elif len(trs) == period:
            smooth = sum(trs) / period; result.append(smooth)
        else:
            smooth = (smooth * (period - 1) + tr) / period; result.append(smooth)
        previous_close = row["close"]
    return result


def fill(price, entering, slippage_bps):
    # Long only: pays up on entry, sells down on exit.
    rate = slippage_bps / 10_000
    return price * (1 + (1 if entering else -1) * rate)


def summarize(trades):
    equity, peak, max_dd, returns = 1.0, 1.0, 0.0, []
    for trade in trades:
        equity *= 1 + trade["net_return"]
        peak = max(peak, equity)
        max_dd = max(max_dd, 1 - equity / peak)
        returns.append(trade["net_return"])
    wins, losses = [x for x in returns if x > 0], [x for x in returns if x < 0]
    gross_profit, gross_loss = sum(wins), -sum(losses)
    return {"trades": len(trades), "win_rate_pct": round(100 * len(wins) / len(trades), 2) if trades else None,
            "expectancy_pct": round(100 * sum(returns) / len(returns), 4) if returns else None,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (None if not gross_profit else "inf"),
            "net_return_pct": round(100 * (equity - 1), 4), "max_drawdown_pct": round(100 * max_dd, 4)}


def run(rows, profile, fee_bps, slippage_bps, stop_atr, target_r, max_hold, min_hold=1):
    """Decision known at bar i's close; entry fills no earlier than bar i+1's
    open. With min_hold=1 (T+1), age>min_hold means the earliest exit is bar
    i+2 -- one full day after the entry fill at bar i+1's open.
    A locked-limit-down bar (high<=down_limit) cannot be sold; such a stop/exit
    is counted as ``blocked`` and the position is carried to the next bar.
    """
    atrs, trades, position, blocked = atr_series(rows), [], None, 0
    min_score = PROFILE_MIN_SCORE[profile]
    for i, bar in enumerate(rows):
        if position is None:
            if i >= len(rows) - 1 or bar["side"] <= 0:   # long only; A股无法裸做空
                continue
            score_raw = bar.get("signal_score")
            score = abs(score_raw if score_raw is not None else 1.0)
            if score < min_score:
                continue
            next_bar = rows[i + 1]
            entry = fill(next_bar["open"], True, slippage_bps)
            distance = max(bar.get("atr") or atrs[i], entry * 0.002) * stop_atr
            stop_raw, target_raw = bar.get("stop"), bar.get("target")
            stop = stop_raw if stop_raw and stop_raw < entry else entry - distance
            target = target_raw if target_raw and target_raw > entry else entry + (entry - stop) * target_r
            position = {"signal_at": bar["timestamp"], "entry_at": next_bar["timestamp"], "entry": entry,
                        "stop": stop, "target": target, "age": 0, "funding": 0.0}
            continue

        position["age"] += 1
        position["funding"] += bar.get("funding_rate") or 0.0   # positive funding paid by a long (融资等场景)
        reason, exit_price = None, None
        can_exit = position["age"] > min_hold
        down_limit = bar.get("down_limit")
        locked_down = down_limit and bar["high"] <= down_limit * 1.000001
        if can_exit and bar["low"] <= position["stop"]:
            if locked_down:
                blocked += 1
            else:
                reason, exit_price = "stop", position["stop"]
        if can_exit and reason is None and bar["high"] >= position["target"]:
            reason, exit_price = "target", position["target"]
        if can_exit and reason is None and position["age"] >= max_hold:
            reason, exit_price = "time", bar["close"]
        if reason:
            exit_fill = fill(exit_price, False, slippage_bps)
            gross = exit_fill / position["entry"] - 1
            costs = 2 * fee_bps / 10_000 + position["funding"]
            trades.append({"entry_at": position["entry_at"], "exit_at": bar["timestamp"], "side": "long",
                           "reason": reason, "gross_return": gross, "cost_return": costs,
                           "net_return": gross - costs})
            position = None
    if position is not None:
        last = rows[-1]
        exit_fill = fill(last["close"], False, slippage_bps)
        gross = exit_fill / position["entry"] - 1
        costs = 2 * fee_bps / 10_000 + position["funding"]
        trades.append({"entry_at": position["entry_at"], "exit_at": last["timestamp"], "side": "long",
                       "reason": "end_of_data", "gross_return": gross, "cost_return": costs,
                       "net_return": gross - costs})
    return {"summary": summarize(trades), "blocked_limit_down_exits": blocked, "trades": trades}


def self_test():
    rows = [
        {"timestamp": "t0", "open": 100, "high": 101, "low": 99, "close": 100, "side": 1, "signal_score": 3},
        {"timestamp": "t1", "open": 100, "high": 103, "low": 99, "close": 102, "side": 0},
        {"timestamp": "t2", "open": 102, "high": 105, "low": 101, "close": 104, "side": 0},
        {"timestamp": "t3", "open": 104, "high": 105, "low": 103, "close": 104, "side": 0},
    ]
    result = run(rows, "balanced", 0, 0, 1, 2, 10)
    assert result["trades"][0]["entry_at"] == "t1", "entry must fill at NEXT bar's open, not the decision bar"
    assert result["summary"]["trades"] == 1 and result["trades"][0]["reason"] == "target"
    # T+1: the entry bar itself (t1, age=1) must not be a valid exit even
    # though its high (103) already clears a typical target.
    assert result["trades"][0]["exit_at"] != "t1"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", nargs="?", help="OHLC决策日志 (.csv/.json/.jsonl)")
    parser.add_argument("--profile", choices=PROFILE_MIN_SCORE, default="balanced")
    parser.add_argument("--fee-bps", type=float, default=5.0, help="单边手续费,基点")
    parser.add_argument("--slippage-bps", type=float, default=3.0, help="单边滑点,基点")
    parser.add_argument("--stop-atr", type=float, default=1.2)
    parser.add_argument("--target-r", type=float, default=2.0)
    parser.add_argument("--max-hold-bars", type=int, default=20)
    parser.add_argument("--min-hold-bars", type=int, default=1, help="T+1近似;当日买入的一根K不可卖出")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(); print("backtest self-test: PASS"); return
    if not args.input:
        parser.error("请提供输入文件，或运行 --self-test")
    result = run(load_rows(Path(args.input)), args.profile, args.fee_bps, args.slippage_bps,
                 args.stop_atr, args.target_r, args.max_hold_bars, args.min_hold_bars)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
