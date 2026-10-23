# tests/test_research_runner.py
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moonface.research import ladder
from moonface.core.bundle import DataBundle
from moonface.kernel import dsr as kernel_dsr
from moonface.kernel.runner import Boundary, run
from moonface.kernel.spec import HypothesisSpec
from moonface.kernel.store import Store
from moonface.kernel.synth import make_candles

ASSET = {"exchange": "x", "symbol": "S", "timeframe": "4h"}
CANDLES = make_candles(1200, seed=7, drift=0.003)


def fake_loader(asset: dict, start_ms: int, end_ms: int) -> DataBundle:
    return DataBundle(candles=CANDLES)


def make_spec(n: int, n_bars: int, exit_name: str = "horizon_hold") -> HypothesisSpec:
    return HypothesisSpec(
        domain="smoke", version=1, asset=ASSET,
        entry={"family": "donchian_break", "params": {"n": n}},
        exit={"name": exit_name, "params": {"n_bars": n_bars, "atr_period": 14}},
        fraction=0.01)


class RunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out"
        self.store = Store(os.path.join(self.tmp.name, "r.db"))
        self.fence_ts = CANDLES[960].timestamp_ms

    def register(self, specs, name="smoke", status="active"):
        self.store.register_domain(name, 1, status, {"assets": [ASSET]},
                                   CANDLES[0].timestamp_ms,
                                   CANDLES[-1].timestamp_ms + 1, self.fence_ts)
        if specs:
            self.store.insert_grid(name, 1, specs)

    def run_runner(self, **kwargs) -> Boundary:
        return run(self.store, fake_loader, out_root=self.out, **kwargs)


class TestBoundaries(RunnerTestCase):
    def test_idle_when_nothing_registered(self):
        self.assertEqual(self.run_runner().kind, "idle")

    def test_blocked_domain_stops_the_drain(self):
        self.register([], name="blocked_one", status="blocked")
        b = self.run_runner()
        self.assertEqual(b.kind, "blocked")
        self.assertEqual(b.domain, "blocked_one")

    def test_budget_boundary(self):
        self.register([make_spec(20, 12), make_spec(55, 24)])
        b = self.run_runner(budget=1)
        self.assertEqual(b.kind, "budget")

    def test_error_rows_terminal_and_domain_gated(self):
        # unknown exit name -> KeyError in stage 1 -> 3 attempts -> error status
        bad = HypothesisSpec(domain="smoke", version=1, asset=ASSET,
                             entry={"family": "donchian_break", "params": {"n": 20}},
                             exit={"name": "no_such_exit", "params": {}},
                             fraction=0.01)
        self.register([bad])
        b = self.run_runner()
        self.assertEqual(b.kind, "errors")
        self.assertEqual(self.store.counts("smoke", 1), {"error": 1})
        self.assertEqual(self.store.domain("smoke", 1)["status"], "awaiting_gate")


class TestFullFlow(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.register([make_spec(20, 12), make_spec(20, 24),
                       make_spec(55, 12), make_spec(55, 24)])

    def drain_to_gate(self) -> Boundary:
        with patch.object(ladder, "SCREEN_MIN_TRADES", 1), \
             patch.object(kernel_dsr, "DSR_THRESHOLD", 0.0):
            return self.run_runner()

    def test_drains_to_awaiting_gate_or_closed(self):
        b = self.drain_to_gate()
        self.assertIn(b.kind, ("awaiting_gate", "closed"))
        counts = self.store.counts("smoke", 1)
        self.assertEqual(counts.get("pending", 0), 0)
        self.assertEqual(counts.get("screened", 0), 0)
        self.assertTrue((self.out / "smoke" / "report_v1.md").exists())

    def test_lockbox_spent_exactly_once(self):
        b = self.drain_to_gate()
        if b.kind != "awaiting_gate":
            self.skipTest("no survivor on this fixture; covered by smoke test")
        self.store.set_domain_status("smoke", 1, "lockbox_open")
        with patch.object(ladder, "LOCKBOX_MIN_MAR", -1e9), \
             patch.object(ladder, "LOCKBOX_MIN_TRADES", 0):
            b2 = self.run_runner()
        self.assertEqual(b2.kind, "closed")
        d = self.store.domain("smoke", 1)
        self.assertTrue(d["lockbox_touched"])
        self.assertEqual(d["status"], "closed_positive")

    def test_no_survivors_closes_negative(self):
        with patch.object(ladder, "SCREEN_MIN_TRADES", 1), \
             patch.object(kernel_dsr, "DSR_THRESHOLD", 1.1):  # impossible bar
            b = self.run_runner()
        self.assertEqual(b.kind, "closed")
        self.assertEqual(self.store.domain("smoke", 1)["status"], "closed_negative")


class TestProvenanceTriple(RunnerTestCase):
    def test_stage1_stamps_the_provenance_triple(self):
        self.register([make_spec(20, 12)])
        self.run_runner()
        rows = self.store.rows("smoke", 1)
        self.assertEqual(len(rows), 1)
        stage_results = rows[0]["stage_results"]
        self.assertIn("registration_hash", stage_results)
        self.assertIn("data_fingerprint", stage_results)
        self.assertIn("code_hash", stage_results)
        self.assertTrue(stage_results["registration_hash"])
        self.assertTrue(stage_results["data_fingerprint"])
        self.assertTrue(stage_results["code_hash"])

    def test_registration_hash_matches_spec_hash(self):
        from moonface.kernel.spec import spec_hash

        spec = make_spec(20, 12)
        self.register([spec])
        self.run_runner()
        rows = self.store.rows("smoke", 1)
        self.assertEqual(rows[0]["stage_results"]["registration_hash"], spec_hash(spec))


def test_stage1_flags_anomalous_r_multiples(tmp_path):
    from moonface.research import ladder
    from moonface.kernel.runner import run
    from moonface.kernel.store import Store
    from moonface.kernel.spec import HypothesisSpec
    from moonface.core.bundle import DataBundle
    from moonface.kernel.synth import make_candles
    from unittest.mock import patch
    from pathlib import Path

    candles = make_candles(1200, seed=7, drift=0.003)
    asset = {"exchange": "x", "symbol": "S", "timeframe": "4h"}
    spec = HypothesisSpec(
        domain="anom", version=1, asset=asset,
        entry={"family": "donchian_break", "params": {"n": 20}},
        exit={"name": "horizon_hold", "params": {"n_bars": 12, "atr_period": 14}},
        fraction=0.01)

    store = Store(str(tmp_path / "r.db"))
    fence_ts = candles[960].timestamp_ms
    store.register_domain("anom", 1, "active", {"assets": [asset]},
                          candles[0].timestamp_ms,
                          candles[-1].timestamp_ms + 1, fence_ts)
    store.insert_grid("anom", 1, [spec])

    def loader(asset, start_ms, end_ms):
        return DataBundle(candles=candles)

    with patch.object(ladder, "R_SANITY_CAP", 0.0001):
        run(store, loader, out_root=Path(tmp_path) / "out")
    counts = store.counts("anom", 1)
    assert counts.get("anomaly", 0) >= 1
    assert counts.get("screened", 0) == 0 and counts.get("oos_pass", 0) == 0


class TestBespokeRunnerGuard(unittest.TestCase):
    def test_generic_run_skips_bespoke_runner_domain(self):
        import tempfile
        from moonface.kernel.runner import run
        from moonface.kernel.store import Store

        with tempfile.TemporaryDirectory() as td:
            store = Store(td + "/s.db")
            store.register_domain("funding_fade_voltarget", 1, "active",
                                  {"runner": "voltarget"}, 1, 2, 2)
            store.insert_grid("funding_fade_voltarget", 1, [])  # grid_size 0 is fine here
            # A loader that would explode if called proves the domain was skipped.
            def loader(asset, start_ms, end_ms):
                raise AssertionError("generic runner must not load bespoke domains")
            b = run(store, loader, out_root=Path(td))
            self.assertEqual(b.kind, "idle")


if __name__ == "__main__":
    unittest.main()
