import random
import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.microscope.events import (
    Event, bootstrap_ci, bucket_report, effect_size, event_outcomes,
    excursions, forward_vol, null_calibration,
)

STEP = 14_400_000
TS0 = 1_600_000_000_000


def _staircase(n=80, flat_until=20):
    candles = []
    for i in range(n):
        close = 100.0 if i <= flat_until else 100.0 + (i - flat_until)
        candles.append(Candle(timestamp_ms=TS0 + i * STEP, open=close,
                              high=close + 1.0, low=close - 1.0,
                              close=close, volume=1.0))
    return candles


class ExcursionsTest(unittest.TestCase):
    def test_long_up_staircase(self):
        candles = _staircase()
        mfe, mae, stop_first = excursions(candles, 20, +1, risk=4.0)
        # window bars 21..62; best high = close(62)+1 = 143
        self.assertAlmostEqual(mfe, (143.0 - 100.0) / 4.0)
        # worst low = close(21)-1 = 100 -> MAE 0
        self.assertAlmostEqual(mae, 0.0)
        # target 104 hit (bar 24 high=105 >= 104... first at close>=103),
        # stop 96 never hit
        self.assertIs(stop_first, False)

    def test_short_up_staircase_stops_out(self):
        candles = _staircase()
        mfe, mae, stop_first = excursions(candles, 20, -1, risk=4.0)
        self.assertIs(stop_first, True)   # stop 104 hit as price rises

    def test_neither_hit_is_none(self):
        candles = _staircase(n=80, flat_until=79)   # flat forever
        _, _, stop_first = excursions(candles, 20, +1, risk=4.0)
        self.assertIsNone(stop_first)


class ForwardVolTest(unittest.TestCase):
    def test_flat_forward_vol_zero(self):
        candles = _staircase(n=80, flat_until=79)
        self.assertAlmostEqual(forward_vol(candles, 20, bars=12), 0.0)

    def test_short_tail_is_none(self):
        candles = _staircase(n=25)
        self.assertIsNone(forward_vol(candles, 20, bars=12))


class EventOutcomesTest(unittest.TestCase):
    def _pool_and_labels(self):
        candles = _staircase()
        pool = {"XUSDT": DataBundle(candles=candles)}
        timestamps = [c.timestamp_ms for c in candles]
        labels = {"XUSDT": ["UP/MID/NEUTRAL"] * len(candles)}
        return pool, labels, timestamps

    def test_long_event_outcome(self):
        pool, labels, timestamps = self._pool_and_labels()
        events = [Event(ts_ms=TS0 + 20 * STEP, symbol="XUSDT", direction=+1)]
        rows = event_outcomes(pool, labels, timestamps, events)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["label"], "UP/MID/NEUTRAL")
        # 12 bars forward: close(32)=112, risk 4 -> 3.0 R
        self.assertAlmostEqual(row["fwd_r_12"], 3.0)
        self.assertIs(row["stop_first"], False)

    def test_unknown_symbol_and_bad_ts_are_dropped(self):
        pool, labels, timestamps = self._pool_and_labels()
        events = [Event(ts_ms=TS0 + 20 * STEP, symbol="NOPE", direction=+1),
                  Event(ts_ms=12345, symbol="XUSDT", direction=+1)]
        self.assertEqual(event_outcomes(pool, labels, timestamps, events), [])

    def test_zero_atr_event_dropped(self):
        flat = [Candle(timestamp_ms=TS0 + i * STEP, open=100.0, high=100.0,
                       low=100.0, close=100.0, volume=1.0) for i in range(60)]
        pool = {"XUSDT": DataBundle(candles=flat)}
        timestamps = [c.timestamp_ms for c in flat]
        labels = {"XUSDT": ["RANGE/MID/NEUTRAL"] * 60}
        events = [Event(ts_ms=TS0 + 30 * STEP, symbol="XUSDT", direction=+1)]
        self.assertEqual(event_outcomes(pool, labels, timestamps, events), [])


def _outcome(label, fwd12, rng):
    return {"symbol": "XUSDT", "ts_ms": 0, "direction": 1, "label": label,
            "fwd_r_6": fwd12 / 2.0, "fwd_r_12": fwd12, "fwd_r_42": fwd12,
            "mfe_r": abs(fwd12), "mae_r": 0.5,
            "stop_first": fwd12 < 0, "fwd_vol": 0.01 + rng.random() * 0.001}


def _planted_outcomes(n_per=80, seed=5):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_per):
        rows.append(_outcome("GOOD", 1.0 + rng.gauss(0.0, 0.3), rng))
        rows.append(_outcome("BAD", -1.0 + rng.gauss(0.0, 0.3), rng))
    return rows


def _iid_outcomes(n=160, seed=6):
    rng = random.Random(seed)
    return [_outcome(rng.choice(["GOOD", "BAD"]), rng.gauss(0.0, 0.5), rng)
            for _ in range(n)]


class BootstrapTest(unittest.TestCase):
    def test_ci_brackets_mean_and_is_deterministic(self):
        rng = random.Random(1)
        vals = [rng.gauss(1.0, 0.5) for _ in range(100)]
        lo, hi = bootstrap_ci(vals, seed=3)
        self.assertLess(lo, sum(vals) / len(vals))
        self.assertGreater(hi, sum(vals) / len(vals))
        self.assertEqual((lo, hi), bootstrap_ci(vals, seed=3))


class BucketReportTest(unittest.TestCase):
    def test_planted_effect_recovered(self):
        report = bucket_report(_planted_outcomes(), seed=1)
        by = {r["label"]: r for r in report}
        self.assertGreater(by["GOOD"]["fwd_r_12_mean"], 0.5)
        self.assertLess(by["BAD"]["fwd_r_12_mean"], -0.5)
        self.assertEqual(by["GOOD"]["verdict"], "DESCRIPTIVE")
        lo, hi = by["GOOD"]["fwd_r_12_ci"]
        self.assertLess(lo, by["GOOD"]["fwd_r_12_mean"])
        self.assertGreater(hi, by["GOOD"]["fwd_r_12_mean"])
        self.assertAlmostEqual(by["BAD"]["p_stop_first"], 1.0, places=1)

    def test_small_bucket_is_insufficient(self):
        rng = random.Random(2)
        rows = [_outcome("TINY", 1.0, rng) for _ in range(10)]
        report = bucket_report(rows, seed=1)
        self.assertEqual(report[0]["verdict"], "INSUFFICIENT_DATA")
        self.assertNotIn("fwd_r_12_mean", report[0])

    def test_unlabeled_bucket_excluded(self):
        rng = random.Random(4)
        rows = _planted_outcomes() + [_outcome("UNLABELED", 5.0, rng)
                                      for _ in range(50)]
        report = bucket_report(rows, seed=1)
        self.assertEqual({r["label"] for r in report}, {"GOOD", "BAD"})
        self.assertEqual(effect_size(rows),
                         effect_size(_planted_outcomes()))


class NullCalibrationTest(unittest.TestCase):
    def test_planted_effect_exceeds_null(self):
        result = null_calibration(_planted_outcomes(), seed=2)
        self.assertEqual(result["verdict"], "EXCEEDS_NULL")
        self.assertGreater(result["real_effect"], 1.0)

    def test_iid_is_indistinguishable(self):
        result = null_calibration(_iid_outcomes(), seed=2)
        self.assertEqual(result["verdict"], "INDISTINGUISHABLE_FROM_NULL")

    def test_underpowered_effect_is_zero(self):
        rng = random.Random(3)
        rows = [_outcome("A", 1.0, rng) for _ in range(10)] + \
               [_outcome("B", -1.0, rng) for _ in range(10)]
        self.assertEqual(effect_size(rows), 0.0)
        result = null_calibration(rows, seed=2)
        self.assertEqual(result["verdict"], "INDISTINGUISHABLE_FROM_NULL")

    def test_deterministic(self):
        a = null_calibration(_planted_outcomes(), seed=9)
        b = null_calibration(_planted_outcomes(), seed=9)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
