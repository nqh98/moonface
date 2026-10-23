# tests/test_orderflow_wf.py
import unittest

from moonface.core.bundle import DataBundle
from moonface.research import orderflow as of
from moonface.research import orderflow_wf as owf
from moonface.kernel.synth import make_candles


def _sweep_spec():
    # price family -> no feature needed for the walk-forward shape test
    s = [x for x in of.orderflow_specs()
         if x.entry["family"] == "liquidity_sweep_reclaim"][0]
    return s, of.control_for(s)


class TestWalkForwardGeometry(unittest.TestCase):
    def test_fold_count_from_geometry(self):
        n = 17280 + 5760 * 3          # train + 3 test windows
        bundle = DataBundle(candles=make_candles(n, seed=3))
        spec, ctrl = _sweep_spec()
        wf = owf.walk_forward(spec, bundle, ctrl)
        expected = len(range(owf.TRAIN_BARS, n - owf.TEST_BARS + 1, owf.STEP_BARS))
        self.assertEqual(wf["folds"], expected)
        self.assertGreaterEqual(expected, 2)

    def test_returns_keys_and_dominance(self):
        n = 17280 + 5760 * 3
        bundle = DataBundle(candles=make_candles(n, seed=3))
        spec, ctrl = _sweep_spec()
        wf = owf.walk_forward(spec, bundle, ctrl)
        for k in ("folds", "aggregate_treatment_mar",
                  "aggregate_treatment_sharpe", "aggregate_control_mar",
                  "aggregate_trades", "dominance"):
            self.assertIn(k, wf)

    def test_too_short_yields_no_folds(self):
        bundle = DataBundle(candles=make_candles(1000, seed=3))
        spec, ctrl = _sweep_spec()
        wf = owf.walk_forward(spec, bundle, ctrl)
        self.assertEqual(wf["folds"], 0)
        self.assertFalse(owf.stage35_of(wf))


class TestStage35Gate(unittest.TestCase):
    def test_passes_on_positive_mar_and_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_control_mar": 0.1,
              "aggregate_trades": 40, "dominance": True}
        self.assertTrue(owf.stage35_of(ok))

    def test_fails_without_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_control_mar": 0.6,
              "aggregate_trades": 40, "dominance": False}
        self.assertFalse(owf.stage35_of(ok))


if __name__ == "__main__":
    unittest.main()
