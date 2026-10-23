# tests/test_voltarget_wf.py
import unittest

from moonface.core.bundle import DataBundle
from moonface.research import voltarget_wf
from moonface.kernel.spec import HypothesisSpec
from moonface.kernel.synth import make_candles
from moonface.research.voltarget import VOLTARGET_ENTRY, VOLTARGET_EXIT


def _spec():
    fam, ep = VOLTARGET_ENTRY
    name, xp = VOLTARGET_EXIT
    return HypothesisSpec(
        domain="funding_fade_voltarget", version=1,
        asset={"exchange": "binance", "symbol": "ETH/USDT:USDT",
               "timeframe": "4h", "funding_symbol": "ETH/USDT:USDT"},
        entry={"family": fam, "params": ep},
        exit={"name": name, "params": xp}, fraction=0.01)


class TestWalkForwardGeometry(unittest.TestCase):
    def test_fold_count_from_geometry(self):
        # n=12000 bars, train=6570, test=step=1095 -> folds where start+1095<=12000
        bundle = DataBundle(candles=make_candles(12000, seed=3),
                            funding=[0.0] * 12000)
        wf = voltarget_wf.walk_forward_paired(_spec(), bundle)
        expected = len(range(6570, 12000 - 1095 + 1, 1095))
        self.assertEqual(wf["folds"], expected)
        self.assertGreaterEqual(expected, 4)

    def test_returns_both_arms_and_dominance(self):
        bundle = DataBundle(candles=make_candles(12000, seed=3),
                            funding=[0.0] * 12000)
        wf = voltarget_wf.walk_forward_paired(_spec(), bundle)
        for k in ("folds", "aggregate_control_mar", "aggregate_treatment_mar",
                  "aggregate_treatment_sharpe", "aggregate_trades", "dominance"):
            self.assertIn(k, wf)

    def test_too_short_window_yields_no_folds(self):
        bundle = DataBundle(candles=make_candles(1000, seed=3),
                            funding=[0.0] * 1000)
        wf = voltarget_wf.walk_forward_paired(_spec(), bundle)
        self.assertEqual(wf["folds"], 0)
        self.assertFalse(voltarget_wf.stage35_paired(wf))


class TestStage35Gate(unittest.TestCase):
    def test_passes_on_positive_mar_and_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_trades": 40,
              "dominance": True}
        self.assertTrue(voltarget_wf.stage35_paired(ok))

    def test_fails_without_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_trades": 40,
              "dominance": False}
        self.assertFalse(voltarget_wf.stage35_paired(ok))


if __name__ == "__main__":
    unittest.main()
