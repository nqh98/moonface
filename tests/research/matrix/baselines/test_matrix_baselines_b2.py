import random
import unittest

from moonface.core.models import Candle
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.strategies import (
    _freeze_flags,
    donchian_reverse,
    donchian_reverse_frozen,
)


def _osc(n, seed=0):
    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        phase = (t // 30) % 2
        px = max(1.0, px + (0.6 if phase == 0 else -0.6) + rng.uniform(-0.1, 0.1))
        out.append(Candle(t * 14_400_000, px, px + 0.5, px - 0.5, px, 10.0))
    return out


class FreezeFlagsTest(unittest.TestCase):
    def test_constant_series_never_frozen(self):
        self.assertFalse(any(_freeze_flags([1.0] * 40, pctl=0.80, lookback=20)))

    def test_spike_bar_is_frozen(self):
        flags = _freeze_flags([1.0] * 40 + [100.0], pctl=0.80, lookback=20)
        self.assertTrue(flags[-1])

    def test_warmup_bars_never_frozen(self):
        self.assertEqual(
            _freeze_flags([1.0] * 10, pctl=0.80, lookback=20), [False] * 10
        )


class Baseline2Test(unittest.TestCase):
    def test_unreachable_pctl_matches_baseline1(self):
        candles = _osc(300)
        b1 = donchian_reverse(candles, n=20, cost=CostModel())
        b2 = donchian_reverse_frozen(
            candles,
            n=20,
            atr_period=14,
            freeze_pctl=1.0,
            freeze_lookback=50,
            cost=CostModel(),
        )
        self.assertEqual(b1, b2)

    def test_heavy_freeze_suppresses_entries(self):
        candles = _osc(300)
        b1 = donchian_reverse(candles, n=20, cost=CostModel())
        heavy = donchian_reverse_frozen(
            candles,
            n=20,
            atr_period=14,
            freeze_pctl=0.0,
            freeze_lookback=50,
            cost=CostModel(),
        )
        self.assertLess(len(heavy), len(b1))


if __name__ == "__main__":
    unittest.main()
