# tests/test_universe_donchian_wf.py
import unittest

from moonface.research.universe_donchian_wf import walk_forward, stage35_of


class TestWalkForward(unittest.TestCase):
    def test_two_non_overlapping_folds_and_dominance(self):
        # 365 warm-up + 182 + 182 = 729 daily returns. Treatment alternates
        # (varies -> Sharpe>0) with positive mean; control flat.
        t = [0.002 if i % 2 == 0 else 0.001 for i in range(729)]
        c = [0.0] * 729
        wf = walk_forward(t, c)
        self.assertEqual(wf["folds"], 2)
        self.assertGreater(wf["aggregate_treatment_mar"], 0.0)
        self.assertTrue(wf["dominance"])

    def test_too_short_for_any_fold(self):
        wf = walk_forward([0.001] * 400, [0.0] * 400)
        self.assertEqual(wf["folds"], 0)
        self.assertFalse(stage35_of(wf))

    def test_stage35_requires_dominance(self):
        # Both vary; control has the higher mean -> control dominates, so the
        # treatment does NOT pass stage35 (needs treatment dominance).
        t = [0.001 if i % 2 == 0 else 0.0005 for i in range(729)]
        c = [0.004 if i % 2 == 0 else 0.003 for i in range(729)]
        wf = walk_forward(t, c)
        self.assertFalse(stage35_of(wf))


if __name__ == "__main__":
    unittest.main()
