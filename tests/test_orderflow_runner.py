# tests/test_orderflow_runner.py
import tempfile
import unittest
from pathlib import Path

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research import orderflow_runner as orunner
from moonface.kernel.store import Store


def _flat_bundle(asset, start_ms, end_ms):
    """Loader stub: constant price + flat feature -> every family is silent ->
    stage 1 (>=100 trades) fails -> closed_negative, lockbox untouched."""
    n = 6000
    candles = [Candle(i * 900_000, 100.0, 100.0, 100.0, 100.0, 1.0) for i in range(n)]
    return DataBundle(candles=candles, feature=[1000.0] * n)


class TestRegister(unittest.TestCase):
    def test_register_creates_bespoke_domain(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            d = store.domain(orunner.ORDERFLOW_DOMAIN, 1)
            self.assertIsNotNone(d)
            self.assertEqual(d["config"].get("runner"), "orderflow")
            self.assertEqual(d["grid_size"], 10)
            self.assertFalse(d["lockbox_touched"])

    def test_register_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            orunner.register(store, now_ms=1_800_000_000_000)   # must not overwrite
            d = store.domain(orunner.ORDERFLOW_DOMAIN, 1)
            self.assertEqual(d["end_ms"], 1_700_000_000_000)


class TestRunDomainNegative(unittest.TestCase):
    def test_flat_data_closes_negative_without_spending_lockbox(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            verdict = orunner.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_negative")
            d = store.domain(orunner.ORDERFLOW_DOMAIN, 1)
            self.assertFalse(d["lockbox_touched"])
            self.assertEqual(d["status"], "closed_negative")
            self.assertTrue((Path(td) / orunner.ORDERFLOW_DOMAIN
                             / "verdict.md").exists())


class TestRunDomainPositive(unittest.TestCase):
    def _stubs(self):
        research_m = {"screen_trades": 120, "screen_expectancy_r": 0.2,
                      "holdout_trades": 40, "holdout_treatment_mar": 0.5,
                      "holdout_treatment_dd": -0.1, "holdout_treatment_sharpe": 0.5,
                      "holdout_control_mar": 0.1, "holdout_control_sharpe": 0.1,
                      "holdout_dominance": True, "research_sharpe": 0.3,
                      "research_skew": 0.0, "research_kurtosis": 3.0,
                      "research_trades": 160}
        wf_m = {"folds": 4, "aggregate_treatment_mar": 0.5,
                "aggregate_treatment_sharpe": 0.4, "aggregate_control_mar": 0.1,
                "aggregate_trades": 40, "dominance": True}
        tail_m = {"tail_trades": 25, "tail_treatment_mar": 1.2,
                  "tail_treatment_dd": -0.2, "tail_treatment_sharpe": 0.6,
                  "tail_control_mar": 0.3, "tail_control_sharpe": 0.2,
                  "tail_dominance": True}
        return research_m, wf_m, tail_m

    def test_all_pass_spends_lockbox_once_and_promotes(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            research_m, wf_m, tail_m = self._stubs()
            with mock.patch.object(orunner, "evaluate_dominant",
                                   return_value=research_m), \
                 mock.patch.object(orunner, "walk_forward",
                                   return_value=wf_m), \
                 mock.patch.object(orunner, "lockbox_dominant",
                                   return_value=tail_m):
                verdict = orunner.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_positive")
            self.assertTrue(store.domain(orunner.ORDERFLOW_DOMAIN, 1)["lockbox_touched"])


if __name__ == "__main__":
    unittest.main()
