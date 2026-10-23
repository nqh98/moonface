"""Screen-stat and verdict tests. block_effect_z is large for a clean positive
drift and ~0 for zero-mean noise; screen_verdict PASSes only when all 5 frozen
conditions hold and FAILs when any single one is violated."""
import unittest

from moonface.research.liq_twap.screen import (
    FLOOR_Z,
    block_effect_z,
    screen_verdict,
)


class TestBlockEffectZ(unittest.TestCase):
    def test_positive_drift_has_large_z(self):
        rets = [0.5] * 200
        self.assertGreater(block_effect_z(rets, block_len=4), FLOOR_Z)

    def test_zero_mean_noise_has_small_z(self):
        rets = [0.5, -0.5] * 200
        self.assertLess(abs(block_effect_z(rets, block_len=4)), FLOOR_Z)

    def test_too_few_events_is_zero(self):
        self.assertEqual(block_effect_z([0.5], block_len=4), 0.0)


def _cells(strong=True):
    out = []
    for k in (1.5, 2.0):
        for h in (1, 2, 3, 4):
            z = 4.0 if (strong and h == 2) else 0.5
            out.append({"k": k, "h": h, "n": 100, "mean_ret_r": 0.1, "effect_z": z})
    return out


class TestScreenVerdict(unittest.TestCase):
    def test_all_conditions_pass(self):
        v = screen_verdict(_cells(), treat_mean=0.20, ctrl_mean=0.05, null_max_z=1.0)
        self.assertTrue(v["passed"], v)

    def test_floor_not_cleared_fails(self):
        v = screen_verdict(_cells(strong=False), treat_mean=0.20, ctrl_mean=0.05, null_max_z=1.0)
        self.assertFalse(v["passed"])
        self.assertFalse(v["conditions"]["floor"])

    def test_treatment_not_above_control_fails(self):
        v = screen_verdict(_cells(), treat_mean=0.05, ctrl_mean=0.20, null_max_z=1.0)
        self.assertFalse(v["passed"])
        self.assertFalse(v["conditions"]["treatment_gt_control"])

    def test_null_clears_floor_fails(self):
        v = screen_verdict(_cells(), treat_mean=0.20, ctrl_mean=0.05, null_max_z=3.5)
        self.assertFalse(v["passed"])
        self.assertFalse(v["conditions"]["null_fails"])

    def test_negative_pooled_sign_fails(self):
        cells = _cells()
        for c in cells:
            c["mean_ret_r"] = -0.1
        v = screen_verdict(cells, treat_mean=0.20, ctrl_mean=0.05, null_max_z=1.0)
        self.assertFalse(v["passed"])
        self.assertFalse(v["conditions"]["sign_positive"])


if __name__ == "__main__":
    unittest.main()
