# tests/test_research_smoke.py
"""Full-ladder smoke on synthetic data: init a tiny custom domain, drain it,
open the gate, spend the lockbox, and confirm the terminal invariants."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moonface.research import ladder
from moonface.core.bundle import DataBundle
from moonface.kernel import dsr as kernel_dsr
from moonface.kernel.runner import run
from moonface.kernel.spec import HypothesisSpec
from moonface.kernel.store import LockboxAlreadyTouchedError, Store
from moonface.kernel.synth import make_candles

ASSET = {"exchange": "x", "symbol": "S", "timeframe": "4h"}
CANDLES = make_candles(1200, seed=11, drift=0.004, noise=0.006)


def loader(asset, start_ms, end_ms):
    return DataBundle(candles=CANDLES)


class TestEndToEnd(unittest.TestCase):
    def test_full_ladder_lifecycle(self):
        tmp = tempfile.TemporaryDirectory()
        out = Path(tmp.name) / "out"
        store = Store(os.path.join(tmp.name, "r.db"))
        specs = [HypothesisSpec(
            domain="smoke", version=1, asset=ASSET,
            entry={"family": "donchian_break", "params": {"n": n}},
            exit={"name": "horizon_hold",
                  "params": {"n_bars": nb, "atr_period": 14}},
            fraction=0.01) for n in (20, 55) for nb in (12, 24)]
        store.register_domain("smoke", 1, "active", {"assets": [ASSET]},
                              CANDLES[0].timestamp_ms,
                              CANDLES[-1].timestamp_ms + 1,
                              CANDLES[960].timestamp_ms)
        store.insert_grid("smoke", 1, specs)

        with patch.object(ladder, "SCREEN_MIN_TRADES", 1), \
             patch.object(kernel_dsr, "DSR_THRESHOLD", 0.0), \
             patch.object(ladder, "LOCKBOX_MIN_MAR", -1e9), \
             patch.object(ladder, "LOCKBOX_MIN_TRADES", 0):
            b1 = run(store, loader, out_root=out)
            self.assertIn(b1.kind, ("awaiting_gate", "closed"))
            if b1.kind == "awaiting_gate":
                store.set_domain_status("smoke", 1, "lockbox_open")
                b2 = run(store, loader, out_root=out)
                self.assertEqual(b2.kind, "closed")
                d = store.domain("smoke", 1)
                self.assertTrue(d["lockbox_touched"])
                self.assertIn(d["status"], ("closed_positive", "closed_negative"))
                # the tail is mechanically unrepeatable
                with self.assertRaises(LockboxAlreadyTouchedError):
                    store.touch_lockbox("smoke", 1)

        # terminal invariants either way
        counts = store.counts("smoke", 1)
        self.assertEqual(counts.get("pending", 0), 0)
        self.assertEqual(counts.get("screened", 0), 0)
        self.assertEqual(counts.get("oos_pass", 0), 0)
        self.assertTrue((out / "smoke" / "report_v1.md").exists())
        report = (out / "smoke" / "report_v1.md").read_text()
        self.assertIn("## Funnel", report)
        self.assertIn("## Decision", report)


if __name__ == "__main__":
    unittest.main()
