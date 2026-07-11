#!/usr/bin/env python3
"""Behavioral tests for scripts/crypto/alert.py and scan.py -- pc.* stubbed, no network.

Both scripts are guarded by `if __name__ == "__main__":`, so importing them here
does not execute anything (no accidental network calls / SystemExit at import time).
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "crypto"))
import alert  # noqa: E402
import perp_core as pc  # noqa: E402
import scan  # noqa: E402


class AlertConfirmClosedTests(unittest.TestCase):
    def test_default_invocation_is_a_live_warning_only(self):
        original_price = pc.okx_price
        alert.pc.okx_price = lambda _sym, _errors: {"last": 99.0, "chg24h_pct": -1.0}
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = alert.main(["ETH", "100", "110"])
        finally:
            alert.pc.okx_price = original_price
        rendered = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("下破预警", rendered)
        self.assertIn("未做已收盘确认", rendered)
        self.assertNotIn("已收盘确认破位", rendered)

    def test_confirm_closed_requires_opt_in_to_confirm(self):
        original_price, original_candles = pc.okx_price, pc.okx_candles
        alert.pc.okx_price = lambda _sym, _errors: {"last": 99.0, "chg24h_pct": -1.0}
        alert.pc.okx_candles = lambda *_a, **_k: {"closes": [102.0, 99.0, 98.0, 97.0, 96.0], "timestamps": [1, 2, 3, 4, 5]}
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = alert.main(["ETH", "100", "110", "--confirm-closed", "5m", "--profile", "conservative"])
        finally:
            alert.pc.okx_price, alert.pc.okx_candles = original_price, original_candles
        self.assertEqual(code, 0)
        self.assertIn("已收盘确认破位", out.getvalue())

    def test_rejects_support_greater_than_resistance(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = alert.main(["ETH", "110", "100"])
        self.assertEqual(code, 2)

    def test_missing_price_does_not_fabricate_a_signal(self):
        original_price = pc.okx_price
        alert.pc.okx_price = lambda _sym, errors: (errors.append("OKX ticker: timeout"), None)[1]
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = alert.main(["ETH", "100", "110"])
        finally:
            alert.pc.okx_price = original_price
        self.assertEqual(code, 1)
        self.assertIn("不要编造", out.getvalue())


class ScanReadyGateTests(unittest.TestCase):
    def test_missing_primary_derivative_excludes_from_ranking(self):
        missing = scan._missing_primary_derivs({
            "funding_rate_8h": 0.0, "oi_usd": 1.0,
            "global_ls": {}, "top_position": {"ratio": None}, "taker_buysell": {"last": None},
        })
        self.assertIn("散户多空比", missing)
        self.assertIn("大户持仓比", missing)
        self.assertIn("Taker", missing)

    def test_complete_derivatives_have_no_missing(self):
        missing = scan._missing_primary_derivs({
            "funding_rate_8h": 0.0, "oi_usd": 1.0,
            "global_ls": {"ratio": 1.0}, "top_position": {"ratio": 1.0}, "taker_buysell": {"last": 1.0},
        })
        self.assertEqual(missing, [])

    def test_partial_data_coin_is_excluded_from_ranked_table(self):
        original = {"price": pc.okx_price, "candles": pc.okx_candles, "levels": pc.build_levels, "derivs": pc.bn_derivs}
        closes = [100.0 + i * 0.01 for i in range(40)]
        scan.pc.okx_price = lambda _s, _e: {"last": closes[-1], "chg24h_pct": 1.0}
        scan.pc.okx_candles = lambda *_a, **_k: {"closes": closes, "highs": [c + 0.1 for c in closes],
                                                  "lows": [c - 0.1 for c in closes], "timestamps": list(range(40)),
                                                  "meta": {}}
        scan.pc.build_levels = original["levels"]
        # BTC: complete derivatives. ETH: missing global_ls ratio -> CAUTION, excluded from ranking.
        def fake_derivs(sym, _period, _errors):
            full = {"funding_rate_8h": 0.0, "oi_usd": 1.0, "oi_trend": 0, "oi_chg_window_pct": 0.0,
                    "global_ls": {"ratio": 1.0, "trend": 0}, "top_position": {"ratio": 1.0, "trend": 0},
                    "top_account": {"ratio": 1.0, "trend": 0}, "taker_buysell": {"last": 1.0, "trend": 0}}
            if sym == "ETH":
                full = dict(full); full["global_ls"] = {"ratio": None, "trend": 0}
            return full
        scan.pc.bn_derivs = fake_derivs
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                scan.main(["BTC,ETH", "15m"])
        finally:
            scan.pc.okx_price, scan.pc.okx_candles = original["price"], original["candles"]
            scan.pc.build_levels, scan.pc.bn_derivs = original["levels"], original["derivs"]
        rendered = out.getvalue()
        self.assertIn("| 1 | BTC |", rendered)
        self.assertIn("数据不全·不参与排名", rendered)
        self.assertNotIn("| 2 | ETH |", rendered)  # ETH must not get a ranked row


if __name__ == "__main__":
    unittest.main()
