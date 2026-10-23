import unittest

from moonface.core.bundle import DataBundle
from moonface.kernel.lockbox import FencedBundle
from moonface.kernel.synth import make_candles


class TestFencedBundle(unittest.TestCase):
    def setUp(self):
        self.candles = make_candles(100, seed=7)
        self.funding = [0.0001 * i for i in range(100)]
        # fence at candle 80's open -> research = candles[0:80]
        self.fence_ts = self.candles[80].timestamp_ms
        self.fb = FencedBundle(
            DataBundle(candles=self.candles, funding=self.funding), self.fence_ts)

    def test_fence_index(self):
        self.assertEqual(self.fb.fence_index, 80)

    def test_research_never_crosses_the_fence(self):
        research = self.fb.research()
        self.assertEqual(len(research.candles), 80)
        self.assertTrue(all(c.timestamp_ms < self.fence_ts for c in research.candles))

    def test_aux_series_sliced_in_lockstep(self):
        research = self.fb.research()
        self.assertEqual(len(research.funding), 80)
        self.assertIsNone(research.basis)

    def test_full_is_complete(self):
        self.assertEqual(len(self.fb.full.candles), 100)

    def test_fence_between_bars_uses_next_bar(self):
        fb = FencedBundle(DataBundle(candles=self.candles),
                          self.candles[80].timestamp_ms - 1)
        self.assertEqual(fb.fence_index, 80)


if __name__ == "__main__":
    unittest.main()
