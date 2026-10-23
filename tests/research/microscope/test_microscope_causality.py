"""Anti-lookahead and determinism regression tests (spec §4.1, §5).

Truncation invariance: every feature, factor, and label at bar t must be
bit-identical when all data after t is removed. If this fails, something
looked ahead — fix the implementation, never this test."""
import random
import unittest

from moonface.core.bundle import DataBundle
from moonface.research.microscope.events import (
    Event, bucket_report, event_outcomes, null_calibration,
)
from moonface.research.microscope.factors import state_vectors
from moonface.research.microscope.features import build_matrix
from moonface.research.microscope.regimes import label_series
from tests.helpers_microscope import STEP_MS, TS0, make_pool


def _truncate(pool, upto):
    return {sym: DataBundle(
                candles=b.candles[: upto + 1],
                funding=b.funding[: upto + 1] if b.funding else None,
                feature=b.feature[: upto + 1] if b.feature else None)
            for sym, b in pool.items()}


class TruncationInvarianceTest(unittest.TestCase):
    def test_features_states_labels_invariant(self):
        pool = make_pool(n=320, n_assets=10, seed=17)
        t_check = 250
        full = build_matrix(pool)
        trunc = build_matrix(_truncate(pool, t_check))
        self.assertEqual(full.timestamps[t_check], trunc.timestamps[-1])
        for sym in full.symbols:
            self.assertEqual(full.rows[sym][t_check],
                             trunc.rows[sym][t_check])
        self.assertEqual(full.mkt_ret_z[t_check],
                         trunc.mkt_ret_z[t_check])
        self.assertEqual(full.breadth_z[t_check],
                         trunc.breadth_z[t_check])
        full_labels = label_series(state_vectors(full))
        trunc_labels = label_series(state_vectors(trunc))
        for sym in full.symbols:
            self.assertEqual(full_labels[sym][t_check],
                             trunc_labels[sym][t_check])


class DeterminismTest(unittest.TestCase):
    def test_same_seed_same_study(self):
        pool = make_pool(n=320, n_assets=10, seed=19)
        m = build_matrix(pool)
        labels = label_series(state_vectors(m))
        events = [Event(ts_ms=TS0 + t * STEP_MS, symbol=sym, direction=+1)
                  for t in range(200, 260, 3)
                  for sym in ("A00USDT", "A05USDT", "BTCUSDT")]
        out1 = event_outcomes(pool, labels, m.timestamps, events)
        out2 = event_outcomes(pool, labels, m.timestamps, events)
        self.assertEqual(out1, out2)
        self.assertEqual(bucket_report(out1, seed=4),
                         bucket_report(out2, seed=4))
        self.assertEqual(null_calibration(out1, seed=4),
                         null_calibration(out2, seed=4))


def _synthetic_outcomes(n_per=40, seed=31):
    """Directly-built outcome rows (bypassing event_outcomes) sized to clear
    POWER_FLOOR=30 per bucket, so bucket_report actually invokes bootstrap_ci
    and null_calibration's shuffle actually varies effect_size — unlike
    test_same_seed_same_study's fixture, which never reaches POWER_FLOOR."""
    rng = random.Random(seed)
    rows = []
    for label, mean in (("GOOD", 1.0), ("BAD", -1.0)):
        for i in range(n_per):
            fwd12 = rng.gauss(mean, 0.3)
            rows.append({
                "symbol": "XUSDT", "ts_ms": i, "direction": 1, "label": label,
                "fwd_r_6": fwd12 / 2.0, "fwd_r_12": fwd12, "fwd_r_42": fwd12,
                "mfe_r": abs(fwd12), "mae_r": 0.5, "stop_first": fwd12 < 0,
                "fwd_vol": 0.01})
    return rows


class BucketAndNullDeterminismTest(unittest.TestCase):
    def test_bucket_and_null_calibration_are_deterministic(self):
        outcomes = _synthetic_outcomes()
        r1 = bucket_report(outcomes, seed=7)
        r2 = bucket_report(outcomes, seed=7)
        self.assertEqual(r1, r2)
        by_label = {b["label"]: b for b in r1}
        self.assertEqual(by_label["GOOD"]["verdict"], "DESCRIPTIVE")
        self.assertIn("fwd_r_12_ci", by_label["GOOD"])
        self.assertEqual(null_calibration(outcomes, seed=7),
                         null_calibration(outcomes, seed=7))


if __name__ == "__main__":
    unittest.main()
