#!/usr/bin/env python3
"""Unit tests for scripts/crypto/backtest.py and scripts/ashare/backtest.py.

Focus: the no-lookahead property explicitly required for this harness --
a decision recorded at bar i's close must fill no earlier than bar i+1's open,
never at bar i itself.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


crypto_bt = _load("crypto_backtest", ROOT / "scripts" / "crypto" / "backtest.py")
ashare_bt = _load("ashare_backtest", ROOT / "scripts" / "ashare" / "backtest.py")


class CryptoBacktestTests(unittest.TestCase):
    def test_self_test(self):
        crypto_bt.self_test()  # raises on failure

    def test_entry_never_fills_on_the_decision_bar(self):
        rows = [
            {"timestamp": "t0", "open": 100, "high": 101, "low": 99, "close": 100, "side": 1, "signal_score": 3},
            {"timestamp": "t1", "open": 100, "high": 103, "low": 99, "close": 102, "side": 0},
            {"timestamp": "t2", "open": 102, "high": 105, "low": 101, "close": 104, "side": 0},
        ]
        result = crypto_bt.run(rows, "balanced", 0, 0, 1, 2, 10)
        self.assertEqual(result["trades"][0]["entry_at"], "t1")

    def test_short_side_is_supported(self):
        rows = [
            {"timestamp": "t0", "open": 100, "high": 101, "low": 99, "close": 100, "side": -1, "signal_score": 3},
            {"timestamp": "t1", "open": 100, "high": 101, "low": 95, "close": 96, "side": 0},
            {"timestamp": "t2", "open": 96, "high": 97, "low": 90, "close": 91, "side": 0},
        ]
        result = crypto_bt.run(rows, "balanced", 0, 0, 1, 2, 10)
        self.assertEqual(result["trades"][0]["side"], "short")
        self.assertGreater(result["trades"][0]["net_return"], 0)

    def test_atr_series_uses_only_past_and_current_bar(self):
        rows = [
            {"open": 100, "high": 105, "low": 95, "close": 100},
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 200, "low": 50, "close": 100},  # a huge future range must not leak backward
        ]
        atrs = crypto_bt.atr_series(rows, period=14)
        self.assertAlmostEqual(atrs[0], 10.0)  # first bar: high-low only, unaffected by bar 2/3
        self.assertLess(atrs[1], atrs[2])      # the big range only shows up once it's "current"


class AshareBacktestTests(unittest.TestCase):
    def test_self_test(self):
        ashare_bt.self_test()  # raises on failure

    def test_entry_never_fills_on_the_decision_bar(self):
        rows = [
            {"timestamp": "d0", "open": 100, "high": 101, "low": 99, "close": 100, "side": 1, "signal_score": 3},
            {"timestamp": "d1", "open": 100, "high": 103, "low": 99, "close": 102, "side": 0},
            {"timestamp": "d2", "open": 102, "high": 105, "low": 101, "close": 104, "side": 0},
        ]
        result = ashare_bt.run(rows, "balanced", 0, 0, 1, 2, 10)
        self.assertEqual(result["trades"][0]["entry_at"], "d1")

    def test_t1_blocks_same_day_exit_even_when_target_would_hit(self):
        # Entry fills at d1's open. d1's own high (103) would hit a typical
        # target, but T+1 means the earliest exit is d2, not d1.
        rows = [
            {"timestamp": "d0", "open": 100, "high": 101, "low": 99, "close": 100, "side": 1, "signal_score": 3},
            {"timestamp": "d1", "open": 100, "high": 130, "low": 99, "close": 102},
            {"timestamp": "d2", "open": 102, "high": 105, "low": 101, "close": 104},
        ]
        result = ashare_bt.run(rows, "balanced", 0, 0, 1, 2, 10, min_hold=1)
        self.assertNotEqual(result["trades"][0]["exit_at"], "d1")

    def test_short_side_input_is_ignored_long_only(self):
        rows = [
            {"timestamp": "d0", "open": 100, "high": 101, "low": 99, "close": 100, "side": -1, "signal_score": 3},
            {"timestamp": "d1", "open": 100, "high": 101, "low": 95, "close": 96, "side": 0},
            {"timestamp": "d2", "open": 96, "high": 97, "low": 90, "close": 91, "side": 0},
        ]
        result = ashare_bt.run(rows, "balanced", 0, 0, 1, 2, 10)
        self.assertEqual(result["trades"], [])  # A股无法裸做空: a short signal opens nothing

    def test_locked_limit_down_blocks_the_stop_exit(self):
        rows = [
            {"timestamp": "d0", "open": 100, "high": 101, "low": 99, "close": 100, "side": 1, "signal_score": 3},
            {"timestamp": "d1", "open": 100, "high": 101, "low": 99, "close": 100},
            {"timestamp": "d2", "open": 91, "high": 91, "low": 90, "close": 91, "down_limit": 91, "stop": 95},
            {"timestamp": "d3", "open": 95, "high": 96, "low": 94, "close": 95},
        ]
        result = ashare_bt.run(rows, "balanced", 0, 0, 1, 2, 10)
        self.assertGreaterEqual(result["blocked_limit_down_exits"], 1)


if __name__ == "__main__":
    unittest.main()
