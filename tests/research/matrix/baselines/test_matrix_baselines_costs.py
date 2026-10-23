import unittest

from moonface.research.matrix.baselines.costs import CostModel


class CostModelTest(unittest.TestCase):
    def test_round_trip_default(self):
        c = CostModel()
        self.assertAlmostEqual(c.round_trip(), (0.0004 + 0.0001) * 2.0, places=12)

    def test_stress_multiplier_doubles(self):
        base = CostModel().round_trip()
        self.assertAlmostEqual(
            CostModel(mult=2.0).round_trip(), 2.0 * base, places=12
        )


if __name__ == "__main__":
    unittest.main()
