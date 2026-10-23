# tests/test_voltarget.py
import unittest

from moonface.core.metrics import EquitySummary
from moonface.research import voltarget


class TestVolFraction(unittest.TestCase):
    def test_equalizes_stop_risk_and_clamps(self):
        # raw = target_risk / atr_frac; cap = MAX_LEVERAGE * atr_frac
        self.assertAlmostEqual(voltarget.vol_fraction(0.02, 0.0002), 0.01)   # raw=0.01
        self.assertAlmostEqual(voltarget.vol_fraction(0.01, 0.0001), 0.01)   # raw=0.01
        # huge target_risk saturates at the leverage cap (5.0 * atr_frac)
        self.assertAlmostEqual(voltarget.vol_fraction(0.02, 10.0), 0.10)     # cap=5*0.02
        # zero target_risk -> zero fraction
        self.assertAlmostEqual(voltarget.vol_fraction(0.02, 0.0), 0.0)

    def test_floor_is_zero(self):
        self.assertGreaterEqual(voltarget.vol_fraction(0.05, 1.0), 0.0)


class TestCalibrateTargetRisk(unittest.TestCase):
    def test_mean_fraction_matches_control(self):
        afs = [0.01, 0.02, 0.005, 0.015]  # varied vols, none saturating at cap
        tr = voltarget.calibrate_target_risk(afs, mean_fraction=0.01)
        mean_f = sum(voltarget.vol_fraction(af, tr) for af in afs) / len(afs)
        self.assertAlmostEqual(mean_f, 0.01, places=6)

    def test_monotone_unique_root(self):
        afs = [0.01, 0.02, 0.03]
        tr = voltarget.calibrate_target_risk(afs, mean_fraction=0.02)
        # double the target -> mean at least as large (non-decreasing)
        tr2 = voltarget.calibrate_target_risk(afs, mean_fraction=0.04)
        m1 = sum(voltarget.vol_fraction(af, tr) for af in afs) / len(afs)
        m2 = sum(voltarget.vol_fraction(af, tr2) for af in afs) / len(afs)
        self.assertLessEqual(m1, m2 + 1e-9)

    def test_empty_returns_zero(self):
        self.assertEqual(voltarget.calibrate_target_risk([]), 0.0)


class TestTreatmentReturns(unittest.TestCase):
    def test_sizes_each_trade_by_vol(self):
        trades = [(1.0, 0.02), (-1.0, 0.01)]   # (R, atr_frac)
        tr = 0.0002
        rets = voltarget.treatment_returns(trades, tr)
        self.assertEqual(len(rets), 2)
        self.assertAlmostEqual(rets[0], voltarget.vol_fraction(0.02, tr) * 1.0)
        self.assertAlmostEqual(rets[1], voltarget.vol_fraction(0.01, tr) * -1.0)


class TestPairedDominance(unittest.TestCase):
    def _es(self, mar, sharpe):
        return EquitySummary(trade_count=10, net_return=mar, max_drawdown=-0.1,
                             mar=mar, sharpe=sharpe, skew=0.0, kurtosis=3.0)

    def test_strict_on_both(self):
        self.assertTrue(voltarget.paired_dominance(self._es(2.0, 0.5),
                                                    self._es(1.0, 0.4)))
        # wins MAR only -> not dominant
        self.assertFalse(voltarget.paired_dominance(self._es(2.0, 0.4),
                                                     self._es(1.0, 0.5)))
        # tie -> not dominant (strict)
        self.assertFalse(voltarget.paired_dominance(self._es(1.0, 0.5),
                                                     self._es(1.0, 0.5)))


class TestEvaluatePaired(unittest.TestCase):
    def _stream(self):
        # (entry_index, R, atr_frac) — 6 trades across bars 0..5, all tradeable
        return [(0, 1.0, 0.02), (1, -0.5, 0.02), (2, 1.0, 0.01),
                (3, -0.5, 0.01), (4, 1.0, 0.02), (5, -0.5, 0.02)]

    def test_returns_both_arms_and_stage_metrics(self):
        m = voltarget.evaluate_paired(self._stream(), split_index=4)
        for k in ("screen_trades", "screen_expectancy_r", "holdout_trades",
                  "holdout_control_mar", "holdout_treatment_mar",
                  "holdout_treatment_dd", "holdout_dominance",
                  "research_sharpe", "research_skew", "research_kurtosis",
                  "research_trades", "research_control_mar",
                  "research_treatment_mar", "target_risk"):
            self.assertIn(k, m)

    def test_screen_expectancy_is_sizing_independent(self):
        # expectancy-R is computed from raw R, identical to summarize_r
        import statistics
        screen_rs = [1.0, -0.5, 1.0, -0.5]
        m = voltarget.evaluate_paired(self._stream(), split_index=4)
        self.assertAlmostEqual(m["screen_expectancy_r"],
                               statistics.fmean(screen_rs))

    def test_iso_calibration_uses_screen_only(self):
        # target_risk calibrated on screen trades (entry_index < split)
        m = voltarget.evaluate_paired(self._stream(), split_index=4)
        screen_afs = [0.02, 0.02, 0.01, 0.01]
        expected_tr = voltarget.calibrate_target_risk(screen_afs)
        self.assertAlmostEqual(m["target_risk"], round(expected_tr, 8))


class TestStageGates(unittest.TestCase):
    def test_stage1_needs_trades_and_positive_expectancy(self):
        self.assertTrue(voltarget.stage1_paired(
            {"screen_trades": 30, "screen_expectancy_r": 0.1}))
        self.assertFalse(voltarget.stage1_paired(
            {"screen_trades": 29, "screen_expectancy_r": 0.1}))
        self.assertFalse(voltarget.stage1_paired(
            {"screen_trades": 30, "screen_expectancy_r": 0.0}))

    def test_stage2_requires_positive_mar_budget_and_dominance(self):
        ok = {"holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.1,
              "holdout_dominance": True}
        self.assertTrue(voltarget.stage2_paired(ok))
        # budget breach
        bad_dd = {**ok, "holdout_treatment_dd": -0.40}
        self.assertFalse(voltarget.stage2_paired(bad_dd))
        # no dominance
        no_dom = {**ok, "holdout_dominance": False}
        self.assertFalse(voltarget.stage2_paired(no_dom))

    def test_stage4_lockbox_gate(self):
        ok = {"tail_treatment_mar": 1.0, "tail_treatment_dd": -0.2,
              "tail_trades": 10, "tail_dominance": True}
        self.assertTrue(voltarget.stage4_paired(ok))
        self.assertFalse(voltarget.stage4_paired({**ok, "tail_treatment_mar": 0.9}))
        self.assertFalse(voltarget.stage4_paired({**ok, "tail_trades": 9}))


class TestPairedResearchAndLockbox(unittest.TestCase):
    def setUp(self):
        from moonface.core.bundle import DataBundle
        from moonface.kernel.synth import make_candles
        # Flat funding => sd==0 => no funding_fade entries => empty stream.
        # Shape/determinism only (network-free, no trade count asserted).
        self.candles = make_candles(400, seed=7)
        self.bundle = DataBundle(candles=self.candles, funding=[0.0] * 400)
        from moonface.kernel.spec import HypothesisSpec
        fam, ep = voltarget.VOLTARGET_ENTRY
        name, xp = voltarget.VOLTARGET_EXIT
        self.spec = HypothesisSpec(
            domain="funding_fade_voltarget", version=1,
            asset={"exchange": "binance", "symbol": "ETH/USDT:USDT",
                   "timeframe": "4h", "funding_symbol": "ETH/USDT:USDT"},
            entry={"family": fam, "params": ep},
            exit={"name": name, "params": xp}, fraction=voltarget.CONTROL_FRACTION)

    def test_research_shape_and_deterministic(self):
        m = voltarget.paired_research(self.spec, self.bundle)
        self.assertEqual(m["research_trades"], 0)   # flat funding -> no entries
        self.assertEqual(m["screen_trades"], 0)
        self.assertEqual(voltarget.paired_research(self.spec, self.bundle), m)

    def test_lockbox_tail_is_post_fence(self):
        fence_index = 320  # 80% of 400
        m = voltarget.paired_lockbox(self.spec, self.bundle, fence_index)
        self.assertEqual(m["tail_trades"], 0)       # flat funding -> no entries
        self.assertIn("tail_treatment_mar", m)


if __name__ == "__main__":
    unittest.main()
