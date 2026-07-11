#!/usr/bin/env python3
"""Unit tests for scripts/crypto/perp_core.py -- no network calls (pc.get is stubbed)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "crypto"))
import perp_core as pc  # noqa: E402


class OkxCandlesConfirmationTests(unittest.TestCase):
    def test_discards_unconfirmed_last_candle_and_reports_meta(self):
        original_get = pc.get
        pc.get = lambda _url: ({"data": [
            ["300", "12", "13", "11", "12.5", "9", "0", "0", "0"],  # newest, still forming
            ["200", "11", "12", "10", "11.5", "8", "0", "0", "1"],
            ["100", "10", "11", "9", "10.5", "7", "0", "0", "1"],
        ]}, None)
        try:
            errors = []
            candles = pc.okx_candles("ETH", "5m", 3, errors)
        finally:
            pc.get = original_get
        self.assertEqual(errors, [])
        self.assertEqual(candles["timestamps"], [100, 200])
        self.assertEqual(candles["closes"], [10.5, 11.5])
        self.assertEqual(candles["meta"]["dropped_unconfirmed"], 1)
        self.assertEqual(candles["meta"]["last_confirmed_ts"], 200)

    def test_all_unconfirmed_is_an_error_not_empty_success(self):
        original_get = pc.get
        pc.get = lambda _url: ({"data": [["100", "10", "11", "9", "10.5", "7", "0", "0", "0"]]}, None)
        try:
            errors = []
            candles = pc.okx_candles("ETH", "5m", 1, errors)
        finally:
            pc.get = original_get
        self.assertIsNone(candles)
        self.assertTrue(any("no confirmed candles" in e for e in errors))


class BuildLevelsTests(unittest.TestCase):
    def test_requires_at_least_30_confirmed_closes(self):
        self.assertIsNone(pc.build_levels({"closes": [1.0, 2.0, 3.0], "highs": [1, 2, 3], "lows": [1, 2, 3],
                                            "timestamps": [1, 2, 3], "meta": {}}))

    def test_ema_warms_up_on_full_history_not_a_truncated_window(self):
        # A step at the start should still be visible in ema21 only when the
        # full history feeds warm-up; a [-30:]-truncated window would have
        # forgotten it entirely for a 40-bar series that steps at bar 5.
        closes = [100.0] * 5 + [110.0] * 35
        highs = [c + 1 for c in closes]; lows = [c - 1 for c in closes]
        cd = {"closes": closes, "highs": highs, "lows": lows,
              "timestamps": list(range(len(closes))), "meta": {}}
        levels = pc.build_levels(cd)
        self.assertIsNotNone(levels)
        full_ema21 = pc.ema(closes, 21)
        truncated_ema21 = pc.ema(closes[-30:], 21)
        self.assertAlmostEqual(levels["ema21"], round(full_ema21, 4))
        self.assertNotAlmostEqual(full_ema21, truncated_ema21, places=2)


class LevelConfirmationTests(unittest.TestCase):
    def test_requires_n_closed_candles_beyond_the_level(self):
        self.assertEqual(pc.level_confirmation([101, 99, 98], 100, 110, 2), "breakdown")
        self.assertEqual(pc.level_confirmation([109, 111], 100, 110, 1), "breakout")
        self.assertIsNone(pc.level_confirmation([99, 101], 100, 110, 2))
        self.assertIsNone(pc.level_confirmation([105], 100, 110, 1))  # inside range


class ProfileConfigTests(unittest.TestCase):
    def test_known_profiles(self):
        self.assertEqual(pc.profile_config("conservative")["confirmed_closes"], 2)
        self.assertEqual(pc.profile_config("balanced")["confirmed_closes"], 1)
        self.assertEqual(pc.profile_config(None)["name"], "balanced")

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            pc.profile_config("unknown")


class SignalRowsTests(unittest.TestCase):
    def test_missing_funding_is_not_rendered_as_a_fabricated_zero(self):
        rows, _total, _bias = pc.signal_rows(100.0, None, {})
        self.assertEqual(rows[0][0], "资金费率")
        self.assertEqual(rows[0][1], "—")  # not "0.0000%/8h"

    def test_ratio_dicts_with_none_ratio_do_not_crash(self):
        # A malformed upstream Binance row can leave {"ratio": None, ...};
        # this used to raise TypeError comparing None > 2.0.
        rows, _total, _bias = pc.signal_rows(100.0, None, {
            "global_ls": {"ratio": None, "trend": 0},
            "top_position": {"ratio": None, "trend": 0},
            "top_account": {"ratio": None},
            "taker_buysell": {"last": None},
        })
        labels = {r[0]: r for r in rows}
        self.assertEqual(labels["散户多空比"][2], "—")
        self.assertEqual(labels["大户持仓比"][2], "—")


class AssessDataQualityTests(unittest.TestCase):
    def _full_inputs(self):
        price = {"last": 100.0}
        levels = {"candles": 40, "last_candle_ts": 1}
        deriv = {"funding_rate_8h": 0.0, "oi_usd": 1.0, "global_ls": {"ratio": 1.0},
                  "top_position": {"ratio": 1.0}, "taker_buysell": {"last": 1.0}, "top_account": {"ratio": 1.0}}
        mtf = [("5m", 1, 50.0, 1.0), ("15m", 1, 50.0, 1.0), ("1H", 1, 50.0, 1.0), ("4H", 1, 50.0, 1.0)]
        return price, levels, deriv, mtf

    def test_ready_when_everything_present(self):
        price, levels, deriv, mtf = self._full_inputs()
        result = pc.assess_data_quality(price, levels, deriv, mtf, depth={"ratio": 1.0},
                                         okx_funding=0.0, bybit_funding_rate=0.0)
        self.assertEqual(result["status"], "READY")

    def test_missing_mtf_leg_forces_no_trade(self):
        price, levels, deriv, mtf = self._full_inputs()
        mtf = list(mtf); mtf[1] = ("15m", None, None, None)
        result = pc.assess_data_quality(price, levels, deriv, mtf, depth={"ratio": 1.0},
                                         okx_funding=0.0, bybit_funding_rate=0.0)
        self.assertEqual(result["status"], "NO_TRADE")
        self.assertIn("15m已收盘多周期", result["core_missing"])

    def test_missing_primary_derivative_forces_no_trade_not_neutral(self):
        price, levels, deriv, mtf = self._full_inputs()
        deriv = dict(deriv); deriv["global_ls"] = {"ratio": None}
        result = pc.assess_data_quality(price, levels, deriv, mtf, depth={"ratio": 1.0},
                                         okx_funding=0.0, bybit_funding_rate=0.0)
        self.assertEqual(result["status"], "NO_TRADE")

    def test_missing_only_optional_source_is_caution_not_no_trade(self):
        price, levels, deriv, mtf = self._full_inputs()
        result = pc.assess_data_quality(price, levels, deriv, mtf, depth=None, okx_funding=None, bybit_funding_rate=None)
        self.assertEqual(result["status"], "CAUTION")


if __name__ == "__main__":
    unittest.main()
