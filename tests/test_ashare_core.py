#!/usr/bin/env python3
"""Unit tests for scripts/ashare/ashare_core.py -- no network calls."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ashare"))
import ashare_core as ac  # noqa: E402


class LhbTaggingTests(unittest.TestCase):
    def test_does_not_assert_verified_institutional_identity(self):
        # EXPLAIN containing "机构" is real text from the source, but it is
        # not a verified investor-identity feed -- the tag must say so and
        # must not out-score a plain net-buy/sell just because of the word.
        tag = ac._t_lhb({"on_list": True, "net_amt": 5e8, "detail": "机构专用"})
        self.assertIn("未核验", tag[0])
        self.assertEqual(tag[1], 0.8)

    def test_non_institutional_seat_gets_same_magnitude_score(self):
        tag = ac._t_lhb({"on_list": True, "net_amt": 5e8, "detail": "营业部"})
        self.assertEqual(tag[1], 0.8)

    def test_absent_returns_none(self):
        self.assertIsNone(ac._t_lhb(None))
        self.assertIsNone(ac._t_lhb({"on_list": False}))


class ProfileConfigTests(unittest.TestCase):
    def test_known_profiles(self):
        self.assertEqual(ac.profile_config("balanced")["label"], "均衡")
        self.assertEqual(ac.profile_config(None)["name"], "balanced")

    def test_returns_a_copy(self):
        config = ac.profile_config("balanced")
        config["label"] = "mutated"
        self.assertEqual(ac.profile_config("balanced")["label"], "均衡")

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            ac.profile_config("unknown")


class AssessDataQualityTests(unittest.TestCase):
    def _full_inputs(self):
        rt = {"price": 100.0}
        tech = {"rsi14": 50.0}
        mtf = [("60分", 1, 55.0), ("日", 1, 55.0), ("周", 1, 55.0), ("月", 1, 55.0)]
        ff = [{"main": 1.0}]
        return rt, tech, mtf, ff

    def test_ready_when_everything_present(self):
        rt, tech, mtf, ff = self._full_inputs()
        result = ac.assess_data_quality(rt, tech, mtf, ff, lhb={"on_list": True})
        self.assertEqual(result["status"], "READY")

    def test_missing_timeframe_forces_no_trade_not_neutral(self):
        rt, tech, mtf, ff = self._full_inputs()
        mtf = list(mtf); mtf[0] = ("60分", None, None)
        result = ac.assess_data_quality(rt, tech, mtf, ff, lhb={"on_list": True})
        self.assertEqual(result["status"], "NO_TRADE")
        self.assertIn("60分周期", result["core_missing"])

    def test_missing_fund_flow_forces_no_trade(self):
        rt, tech, mtf, ff = self._full_inputs()
        result = ac.assess_data_quality(rt, tech, mtf, ff=None, lhb={"on_list": True})
        self.assertEqual(result["status"], "NO_TRADE")

    def test_missing_lhb_only_is_caution_not_no_trade(self):
        rt, tech, mtf, ff = self._full_inputs()
        result = ac.assess_data_quality(rt, tech, mtf, ff, lhb=None)
        self.assertEqual(result["status"], "CAUTION")


if __name__ == "__main__":
    unittest.main()
