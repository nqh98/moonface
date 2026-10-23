# tests/test_voltarget_runner.py
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from moonface.core.bundle import DataBundle
from moonface.research import voltarget_runner as vr
from moonface.kernel.store import Store
from moonface.kernel.synth import make_candles


def _flat_bundle(asset, start_ms, end_ms):
    """Loader stub: flat funding -> no funding_fade entries -> stage 1 fails."""
    candles = make_candles(6000, seed=11)
    return DataBundle(candles=candles, funding=[0.0] * len(candles))


class TestRegister(unittest.TestCase):
    def test_register_creates_domain_with_bespoke_runner_config(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertIsNotNone(d)
            self.assertEqual(d["config"].get("runner"), "voltarget")
            self.assertEqual(d["grid_size"], 2)         # ETH + SOL
            self.assertFalse(d["lockbox_touched"])

    def test_register_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            vr.register(store, now_ms=1_800_000_000_000)  # must not overwrite
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertEqual(d["end_ms"], 1_700_000_000_000)


class TestRunDomainNegativePath(unittest.TestCase):
    def test_flat_funding_closes_negative_without_spending_lockbox(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            verdict = vr.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_negative")
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertFalse(d["lockbox_touched"])      # never earned the tail
            self.assertEqual(d["status"], "closed_negative")
            self.assertTrue((Path(td) / vr.VOLTARGET_DOMAIN / "verdict.md").exists())


class TestRunDomainPositivePath(unittest.TestCase):
    def _stub(self):
        """Force every stage to pass so we exercise lockbox spend + promotion."""
        research_m = {"screen_trades": 40, "screen_expectancy_r": 0.2,
                      "holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.1,
                      "holdout_dominance": True, "research_sharpe": 0.3,
                      "research_skew": 0.0, "research_kurtosis": 3.0,
                      "research_trades": 80, "research_control_mar": 0.1,
                      "research_treatment_mar": 0.5, "target_risk": 1e-05}
        wf_m = {"folds": 4, "aggregate_control_mar": 0.1,
                "aggregate_treatment_mar": 0.5, "aggregate_treatment_sharpe": 0.4,
                "aggregate_trades": 40, "dominance": True}
        tail_m = {"tail_trades": 20, "tail_control_mar": 0.5,
                  "tail_treatment_mar": 1.2, "tail_treatment_dd": -0.2,
                  "tail_dominance": True, "target_risk": 1e-05}
        return research_m, wf_m, tail_m

    def test_all_pass_spends_lockbox_once_and_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            research_m, wf_m, tail_m = self._stub()
            with mock.patch.object(vr, "paired_research", return_value=research_m), \
                 mock.patch.object(vr, "walk_forward_paired", return_value=wf_m), \
                 mock.patch.object(vr, "paired_lockbox", return_value=tail_m):
                verdict = vr.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_positive")
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertTrue(d["lockbox_touched"])       # spent exactly once


if __name__ == "__main__":
    unittest.main()
