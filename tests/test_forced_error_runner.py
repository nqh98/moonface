import unittest
from pathlib import Path
import tempfile
from unittest import mock

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.forced_error import forced_error_specs
from moonface.research import forced_error_runner as fr
from moonface.kernel.store import Store


class _FakeStore:
    """Minimal in-memory stand-in for Store, matching the runner's calls."""
    def __init__(self):
        self._domain = None
        self._rows = []
        self.lockbox_touched = 0
        self.status = None

    def domain(self, name, version):
        return self._domain

    def register_domain(self, name, version, status, meta, start, end, fence):
        self._domain = {"start_ms": start, "end_ms": end, "fence_ts": fence}

    def insert_grid(self, name, version, specs):
        from moonface.kernel.spec import canonical_json
        self._rows = [{"spec_json": canonical_json(s)} for s in specs]

    def rows(self, name, version):
        return self._rows

    def touch_lockbox(self, name, version):
        self.lockbox_touched += 1

    def set_domain_status(self, name, version, verdict):
        self.status = verdict


def _flat_bundle(n=400):
    cs = [Candle(timestamp_ms=i * 3_600_000, open=9, high=10, low=8, close=9,
                 volume=100.0) for i in range(n)]
    return DataBundle(candles=cs, feature=[100.0] * n, funding=[-0.001] * n)


class TestForcedErrorRunner(unittest.TestCase):
    def test_flat_market_closes_negative_without_touching_lockbox(self):
        store = _FakeStore()
        now = 400 * 3_600_000 + fr.FORCED_ERROR_START_MS
        fr.register(store, now)
        self.assertEqual(len(store.rows(fr.FORCED_ERROR_DOMAIN, 1)),
                         len(forced_error_specs()))

        def loader(asset, start_ms, end_ms):
            return _flat_bundle()

        with tempfile.TemporaryDirectory() as d:
            verdict = fr.run_domain(store, loader, Path(d))
            self.assertEqual(verdict, "closed_negative")
            self.assertTrue((Path(d) / "forced_error" / "verdict.md").exists())
        self.assertEqual(store.lockbox_touched, 0)
        self.assertEqual(store.status, "closed_negative")

    def test_loader_asset_is_union_of_heterogeneous_spec_assets(self):
        # Setup 1 specs carry OI only; Setup 2 specs carry OI + funding. The
        # runner must load ONE bundle from the UNION so failed_fade_squeeze sees
        # funding (regression: loading specs[0].asset gave funding=None ->
        # "requires both OI feature and funding" at the real run).
        store = _FakeStore()
        now = 400 * 3_600_000 + fr.FORCED_ERROR_START_MS
        fr.register(store, now)
        seen = {}

        def loader(asset, start_ms, end_ms):
            seen.update(asset)
            return _flat_bundle()

        with tempfile.TemporaryDirectory() as d:
            fr.run_domain(store, loader, Path(d))
        self.assertEqual(seen.get("metrics_field"), "sum_open_interest")
        self.assertEqual(seen.get("funding_symbol"), "BTC/USDT:USDT")


class TestForcedErrorRunnerPositive(unittest.TestCase):
    """Positive path: every stage is stubbed to pass so a survivor reaches the
    single guarded touch_lockbox and the domain closes positive. Uses a REAL
    Store, so a second touch would raise LockboxAlreadyTouchedError — the
    'touched exactly once' invariant is enforced by the store itself."""

    def _stubs(self):
        # All 8 rows share these research metrics. Identical trial sharpes ->
        # zero trial-SR variance -> expected_max_sharpe == 0 -> sr0 == 0, so
        # research_sharpe=0.3 over 160 obs clears DSR_THRESHOLD (0.95).
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
        null_m = {"passed": True, "p_value": 0.0, "real_mar": 1.0, "draws": 200}
        tail_m = {"tail_trades": 25, "tail_treatment_mar": 1.2,
                  "tail_treatment_dd": -0.2, "tail_treatment_sharpe": 0.6,
                  "tail_control_mar": 0.3, "tail_control_sharpe": 0.2,
                  "tail_dominance": True}
        return research_m, wf_m, null_m, tail_m

    def test_all_pass_spends_lockbox_once_and_promotes(self):
        research_m, wf_m, null_m, tail_m = self._stubs()

        def loader(asset, start_ms, end_ms):
            return _flat_bundle()

        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            now = 400 * 3_600_000 + fr.FORCED_ERROR_START_MS
            fr.register(store, now)
            with mock.patch.object(fr, "evaluate_dominant",
                                   return_value=research_m), \
                 mock.patch.object(fr, "walk_forward", return_value=wf_m), \
                 mock.patch.object(fr, "surrogate_null", return_value=null_m), \
                 mock.patch.object(fr, "lockbox_dominant", return_value=tail_m):
                verdict = fr.run_domain(store, loader, Path(td))
            self.assertEqual(verdict, "closed_positive")
            d = store.domain(fr.FORCED_ERROR_DOMAIN, 1)
            self.assertTrue(d["lockbox_touched"])
            self.assertEqual(d["status"], "closed_positive")
            self.assertTrue((Path(td) / fr.FORCED_ERROR_DOMAIN
                             / "verdict.md").exists())


if __name__ == "__main__":
    unittest.main()
