import unittest

from moonface.core.models import Candle
from moonface.research.matrix.causal.features import (
    FEATURE_NAMES, CausalFeatureExtractor)


def _candles(n):
    out = []
    px = 100.0
    for t in range(n):
        px += (1.0 if t % 3 else -0.7)
        out.append(Candle(timestamp_ms=t * 3600_000, open=px, high=px + 1.0,
                          low=px - 1.0, close=px, volume=10.0))
    return out


class CausalFeatureTest(unittest.TestCase):
    def test_extract_shape_and_names(self):
        ex = CausalFeatureExtractor()
        candles = _candles(200)
        funding = [0.0001] * 200
        vec = ex.extract(candles, funding, 150)
        self.assertEqual(len(vec), len(FEATURE_NAMES))
        self.assertTrue(all(isinstance(v, float) for v in vec))

    def test_features_are_causal(self):
        """Feature at bar i must not change when future bars are mutated/appended."""
        ex = CausalFeatureExtractor()
        candles = _candles(200)
        funding = [0.0001] * 200
        i = 150
        before = ex.extract(candles, funding, i)
        candles[180] = Candle(candles[180].timestamp_ms, 9e9, 9e9, 9e9, 9e9, 9e9)
        funding[190] = 5.0
        extended = candles + _candles(20)
        after = ex.extract(extended, funding + [9.0] * 20, i)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
