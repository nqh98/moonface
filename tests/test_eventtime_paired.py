import unittest

from moonface.kernel.synth import make_candles
from moonface.research.eventtime.paired import (
    EXIT_ROWS,
    arm_metrics,
    curve_stats,
    paired_verdict,
    run_ladder,
)


class TestExitRows(unittest.TestCase):
    def test_registry_flattens_to_ten_rows(self):
        self.assertEqual(len(EXIT_ROWS), 10)


class TestCurveStats(unittest.TestCase):
    def test_additive_r_curve_uses_peak_to_trough_drawdown(self):
        self.assertEqual(curve_stats([1.0, -3.0, 2.0]), (0.0, -3.0))


class TestArmMetrics(unittest.TestCase):
    def test_returns_one_row_per_exit_and_ratio_matches_definition(self):
        rows = arm_metrics(make_candles(1200, seed=7, drift=0.003), {"n": 20})

        self.assertEqual(len(rows), 10)
        for row in rows:
            self.assertEqual(
                set(row),
                {"exit", "params", "trades", "net_r", "max_dd_r", "ratio"},
            )
            if row["net_r"] > 0:
                self.assertAlmostEqual(
                    row["ratio"],
                    abs(row["max_dd_r"]) / row["net_r"],
                )
            else:
                self.assertIsNone(row["ratio"])


class TestPairedVerdict(unittest.TestCase):
    def test_requires_improvement_and_ladder_pass(self):
        clock_rows = [{
            "exit": "fixed_bracket",
            "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0},
            "trades": 10,
            "net_r": 10.0,
            "max_dd_r": -6.0,
            "ratio": 0.6,
        }]
        dollar_rows = [{
            "exit": "fixed_bracket",
            "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0},
            "trades": 10,
            "net_r": 8.0,
            "max_dd_r": -2.0,
            "ratio": 0.25,
        }]

        passed = paired_verdict(
            clock_rows,
            dollar_rows,
            {"ladder_pass": True, "passing_exits": ["fixed_bracket"]},
        )
        failed = paired_verdict(
            clock_rows,
            dollar_rows,
            {"ladder_pass": False, "passing_exits": ["fixed_bracket"]},
        )

        self.assertTrue(passed["pass"])
        self.assertFalse(failed["pass"])


class TestRunLadder(unittest.TestCase):
    def test_returns_ladder_pass_and_passing_exits(self):
        result = run_ladder(make_candles(1200, seed=7, drift=0.003), {"n": 20})

        self.assertIn("ladder_pass", result)
        self.assertIn("passing_exits", result)


if __name__ == "__main__":
    unittest.main()
