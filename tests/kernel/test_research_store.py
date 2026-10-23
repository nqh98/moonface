# tests/test_research_store.py
import os
import tempfile
import unittest

from moonface.kernel.spec import HypothesisSpec, spec_hash
from moonface.kernel.store import (GridFrozenError, LockboxAlreadyTouchedError,
                                     MAX_ATTEMPTS, Store, TransitionError)

ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"}


def make_spec(n: int) -> HypothesisSpec:
    return HypothesisSpec(
        domain="d", version=1, asset=ASSET,
        entry={"family": "donchian_break", "params": {"n": n}},
        exit={"name": "horizon_hold", "params": {"n_bars": 24, "atr_period": 14}},
        fraction=0.01,
    )


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.tmp.name, "r.db"))
        self.store.register_domain("d", 1, "active", {"assets": [ASSET]},
                                   start_ms=0, end_ms=1000, fence_ts=800)
        self.specs = [make_spec(20), make_spec(55)]
        self.store.insert_grid("d", 1, self.specs)
        self.h = spec_hash(self.specs[0])


class TestDomains(StoreTestCase):
    def test_register_and_read_back(self):
        d = self.store.domain("d", 1)
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["grid_size"], 2)
        self.assertEqual(d["fence_ts"], 800)
        self.assertFalse(d["lockbox_touched"])

    def test_unknown_domain_is_none(self):
        self.assertIsNone(self.store.domain("nope", 1))

    def test_domains_in_order(self):
        self.store.register_domain("e", 1, "blocked", {}, 0, 1000, 800)
        names = [d["name"] for d in self.store.domains_in_order()]
        self.assertEqual(names, ["d", "e"])

    def test_grid_freeze(self):
        with self.assertRaises(GridFrozenError):
            self.store.insert_grid("d", 1, [make_spec(100)])

    def test_lockbox_touch_is_set_once(self):
        self.store.touch_lockbox("d", 1)
        self.assertTrue(self.store.domain("d", 1)["lockbox_touched"])
        with self.assertRaises(LockboxAlreadyTouchedError):
            self.store.touch_lockbox("d", 1)

    def test_set_domain_status_validates(self):
        with self.assertRaises(ValueError):
            self.store.set_domain_status("d", 1, "bogus")


class TestHypotheses(StoreTestCase):
    def test_grid_inserted_pending(self):
        rows = self.store.rows("d", 1, status="pending")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["stage_results"], {})

    def test_legal_transition_merges_results(self):
        self.store.advance(self.h, "screened", {"screen_trades": 42})
        self.store.advance(self.h, "oos_pass", {"holdout_mar": 1.2})
        row = self.store.row(self.h)
        self.assertEqual(row["status"], "oos_pass")
        self.assertEqual(row["stage_results"],
                         {"screen_trades": 42, "holdout_mar": 1.2})

    def test_illegal_transition_raises(self):
        with self.assertRaises(TransitionError):
            self.store.advance(self.h, "lockbox_pass", {})

    def test_errors_terminal_after_max_attempts(self):
        for i in range(MAX_ATTEMPTS):
            self.store.record_error(self.h, f"boom {i}")
        row = self.store.row(self.h)
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["attempts"], MAX_ATTEMPTS)
        self.assertIn("boom", row["error"])

    def test_error_below_cap_keeps_status(self):
        self.store.record_error(self.h, "boom")
        row = self.store.row(self.h)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["attempts"], 1)

    def test_counts(self):
        self.store.advance(self.h, "rejected", {})
        c = self.store.counts("d", 1)
        self.assertEqual(c, {"pending": 1, "rejected": 1})


def test_pending_can_transition_to_anomaly(tmp_path):
    from moonface.kernel.spec import HypothesisSpec, spec_hash
    from moonface.kernel.store import Store, TransitionError

    store = Store(str(tmp_path / "r.db"))
    spec = HypothesisSpec(
        domain="d", version=1,
        asset={"exchange": "binance", "symbol": "BTC/USDT:USDT",
               "timeframe": "4h"},
        entry={"family": "donchian_break", "params": {"n": 20}},
        exit={"name": "horizon_hold", "params": {"atr_period": 14,
                                                 "n_bars": 12}},
        fraction=0.01)
    store.register_domain("d", 1, "active", {}, 0, 1, 0)
    store.insert_grid("d", 1, [spec])
    h = spec_hash(spec)
    store.advance(h, "anomaly", {"max_abs_r": 25.0})
    assert store.row(h)["status"] == "anomaly"
    # anomaly is terminal: no further transition allowed
    try:
        store.advance(h, "screened", {})
        assert False, "anomaly must be terminal"
    except TransitionError:
        pass


if __name__ == "__main__":
    unittest.main()
