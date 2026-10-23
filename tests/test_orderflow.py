# tests/test_orderflow.py
import unittest

from moonface.core.bundle import DataBundle
from moonface.research import orderflow as of
from moonface.kernel.synth import make_candles


class TestSpecGrid(unittest.TestCase):
    def test_ten_treatment_specs_two_controls(self):
        specs = of.orderflow_specs()
        self.assertEqual(len(specs), 10)
        self.assertEqual(of.N_TRIALS, 10)
        families = [s.entry["family"] for s in specs]
        self.assertEqual(families.count("oi_flush_reversal"), 4)
        self.assertEqual(families.count("taker_flow_momentum"), 4)
        self.assertEqual(families.count("liquidity_sweep_reclaim"), 2)
        # oi_flush/taker carry a metrics_field; sweep does not
        oi = [s for s in specs if s.entry["family"] == "oi_flush_reversal"][0]
        self.assertEqual(oi.asset["metrics_field"], "sum_open_interest")
        tk = [s for s in specs if s.entry["family"] == "taker_flow_momentum"][0]
        self.assertEqual(tk.asset["metrics_field"],
                         "sum_taker_long_short_vol_ratio")
        sw = [s for s in specs if s.entry["family"] == "liquidity_sweep_reclaim"][0]
        self.assertNotIn("metrics_field", sw.asset)
        # every treatment spec uses the frozen exit + fraction
        for s in specs:
            self.assertEqual(s.exit["name"], "fixed_bracket")
            self.assertEqual(s.exit["params"],
                             {"atr_period": 14, "k_stop": 2.0, "m_tp": 1.0})
            self.assertEqual(s.fraction, of.ORDERFLOW_FRACTION)


class TestControlFor(unittest.TestCase):
    def test_pairs_by_horizon(self):
        spec48 = [s for s in of.orderflow_specs()
                  if s.entry["params"].get("window") == 48
                  or s.entry["params"].get("swing_n") == 48][0]
        spec96 = [s for s in of.orderflow_specs()
                  if s.entry["params"].get("window") == 96
                  or s.entry["params"].get("swing_n") == 96][0]
        c48 = of.control_for(spec48)
        c96 = of.control_for(spec96)
        self.assertEqual(c48.entry["family"], "donchian_break")
        self.assertEqual(c48.entry["params"], {"n": 48, "long_only": False})
        self.assertEqual(c96.entry["params"]["n"], 96)
        # control is a price family: no metrics_field
        self.assertNotIn("metrics_field", c48.asset)


class TestDominates(unittest.TestCase):
    def test_strict_on_mar_and_sharpe(self):
        self.assertTrue(of.dominates(2.0, 0.5, 1.0, 0.4))
        self.assertFalse(of.dominates(2.0, 0.4, 1.0, 0.5))   # sharpe loses
        self.assertFalse(of.dominates(1.0, 0.5, 1.0, 0.5))   # tie -> not strict


class TestStageGates(unittest.TestCase):
    def test_stage1_uses_100_floor(self):
        self.assertTrue(of.stage1_of({"screen_trades": 100,
                                      "screen_expectancy_r": 0.1}))
        self.assertFalse(of.stage1_of({"screen_trades": 99,
                                       "screen_expectancy_r": 0.1}))
        self.assertFalse(of.stage1_of({"screen_trades": 100,
                                       "screen_expectancy_r": 0.0}))

    def test_stage2_needs_mar_budget_dominance(self):
        ok = {"holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.1,
              "holdout_dominance": True}
        self.assertTrue(of.stage2_of(ok))
        self.assertFalse(of.stage2_of({**ok, "holdout_treatment_dd": -0.40}))
        self.assertFalse(of.stage2_of({**ok, "holdout_dominance": False}))

    def test_stage4_lockbox_gate(self):
        ok = {"tail_treatment_mar": 1.0, "tail_treatment_dd": -0.2,
              "tail_trades": 20, "tail_dominance": True}
        self.assertTrue(of.stage4_of(ok))
        self.assertFalse(of.stage4_of({**ok, "tail_treatment_mar": 0.9}))
        self.assertFalse(of.stage4_of({**ok, "tail_trades": 19}))
        self.assertFalse(of.stage4_of({**ok, "tail_dominance": False}))


class TestEvaluateDominant(unittest.TestCase):
    def setUp(self):
        # Flat OI feature -> oi_flush_reversal is silent (sd==0 -> z is None).
        # Shape/determinism only (network-free, no trade count asserted for the
        # control, which is donchian on a synthetic random walk).
        self.candles = make_candles(400, seed=7)
        self.bundle = DataBundle(candles=self.candles, feature=[1000.0] * 400)
        oi = [s for s in of.orderflow_specs()
              if s.entry["family"] == "oi_flush_reversal"][0]
        self.spec = oi
        self.control = of.control_for(oi)

    def test_returns_expected_keys(self):
        m = of.evaluate_dominant(self.spec, self.control, self.bundle)
        for k in ("screen_trades", "screen_expectancy_r", "holdout_trades",
                  "holdout_treatment_mar", "holdout_treatment_dd",
                  "holdout_treatment_sharpe", "holdout_control_mar",
                  "holdout_control_sharpe", "holdout_dominance",
                  "research_sharpe", "research_skew", "research_kurtosis",
                  "research_trades"):
            self.assertIn(k, m)

    def test_flat_feature_treatment_is_silent_and_deterministic(self):
        m = of.evaluate_dominant(self.spec, self.control, self.bundle)
        self.assertEqual(m["screen_trades"], 0)      # flat OI -> no oi_flush entries
        self.assertEqual(m["research_trades"], 0)
        self.assertEqual(
            of.evaluate_dominant(self.spec, self.control, self.bundle), m)

    def test_lockbox_dominant_keys(self):
        m = of.lockbox_dominant(self.spec, self.control, self.bundle, fence_index=320)
        for k in ("tail_trades", "tail_treatment_mar", "tail_treatment_dd",
                  "tail_treatment_sharpe", "tail_control_mar",
                  "tail_control_sharpe", "tail_dominance"):
            self.assertIn(k, m)


if __name__ == "__main__":
    unittest.main()
