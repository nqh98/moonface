import unittest
from moonface.research.forced_error import (
    N_TRIALS, forced_error_specs, control_for,
    ablation_for, stage1_of, stage2_of, stage4_of)


class TestForcedErrorSpecs(unittest.TestCase):
    def test_grid_is_eight_pooled_trials(self):
        specs = forced_error_specs()
        self.assertEqual(len(specs), 8)
        self.assertEqual(N_TRIALS, 8)
        fams = {s.entry["family"] for s in specs}
        self.assertEqual(fams, {"failed_breakout_harvest", "failed_fade_squeeze"})

    def test_setup1_specs_carry_oi_only_and_use_volume(self):
        s1 = [s for s in forced_error_specs()
              if s.entry["family"] == "failed_breakout_harvest"]
        self.assertEqual(len(s1), 4)
        for s in s1:
            self.assertTrue(s.entry["params"]["use_volume"])
            self.assertEqual(s.asset["metrics_field"], "sum_open_interest")
            self.assertNotIn("funding_symbol", s.asset)

    def test_setup2_specs_carry_oi_and_funding(self):
        s2 = [s for s in forced_error_specs()
              if s.entry["family"] == "failed_fade_squeeze"]
        self.assertEqual(len(s2), 4)
        for s in s2:
            self.assertEqual(s.asset["metrics_field"], "sum_open_interest")
            self.assertEqual(s.asset["funding_symbol"], "BTC/USDT:USDT")

    def test_grid_axes(self):
        for s in forced_error_specs():
            self.assertIn(s.entry["params"]["lookback"], (3, 6))
            self.assertIn(s.entry["params"]["k"], (1.5, 2.0))
            self.assertEqual(s.entry["params"]["window"], 180)

    def test_control_and_ablation_mapping(self):
        for s in forced_error_specs():
            c = control_for(s)
            if s.entry["family"] == "failed_breakout_harvest":
                self.assertEqual(c.entry["family"], "failed_breakout_naive")
                a = ablation_for(s)
                self.assertEqual(a.entry["family"], "failed_breakout_harvest")
                self.assertFalse(a.entry["params"]["use_volume"])
            else:
                self.assertEqual(c.entry["family"], "funding_fade_long")
            self.assertEqual(c.exit, s.exit)
            self.assertEqual(c.fraction, s.fraction)


class TestForcedErrorGates(unittest.TestCase):
    def test_stage1(self):
        self.assertTrue(stage1_of({"screen_trades": 30, "screen_expectancy_r": 0.1}))
        self.assertFalse(stage1_of({"screen_trades": 29, "screen_expectancy_r": 0.1}))
        self.assertFalse(stage1_of({"screen_trades": 40, "screen_expectancy_r": 0.0}))

    def test_stage2_needs_dominance(self):
        base = {"holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.2}
        self.assertTrue(stage2_of({**base, "holdout_dominance": True}))
        self.assertFalse(stage2_of({**base, "holdout_dominance": False}))
        self.assertFalse(stage2_of({"holdout_treatment_mar": 0.5,
                                    "holdout_treatment_dd": -0.4,
                                    "holdout_dominance": True}))

    def test_stage4(self):
        ok = {"tail_treatment_mar": 1.2, "tail_treatment_dd": -0.2,
              "tail_trades": 25, "tail_dominance": True}
        self.assertTrue(stage4_of(ok))
        self.assertFalse(stage4_of({**ok, "tail_trades": 19}))
        self.assertFalse(stage4_of({**ok, "tail_dominance": False}))


if __name__ == "__main__":
    unittest.main()
