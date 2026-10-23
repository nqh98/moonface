import unittest

from moonface.kernel.synth import make_candles


class TestMakeCandles(unittest.TestCase):
    def test_deterministic_for_same_seed(self):
        a = make_candles(50, seed=7)
        b = make_candles(50, seed=7)
        self.assertEqual(a, b)

    def test_different_seed_differs(self):
        self.assertNotEqual(make_candles(50, seed=7), make_candles(50, seed=8))

    def test_ohlc_invariants(self):
        for c in make_candles(200, seed=3):
            self.assertGreaterEqual(c.high, max(c.open, c.close))
            self.assertLessEqual(c.low, min(c.open, c.close))
            self.assertGreater(c.low, 0.0)

    def test_timestamps_evenly_spaced(self):
        candles = make_candles(10, seed=1, timeframe_ms=14_400_000)
        deltas = {b.timestamp_ms - a.timestamp_ms
                  for a, b in zip(candles, candles[1:])}
        self.assertEqual(deltas, {14_400_000})

    def test_positive_drift_trends_up(self):
        candles = make_candles(500, seed=2, drift=0.004, noise=0.004)
        self.assertGreater(candles[-1].close, candles[0].close)


if __name__ == "__main__":
    unittest.main()
