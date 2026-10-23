import random
import unittest

from moonface.core.models import Candle
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.strategies import (
    donchian_reverse,
)


def _osc(n, seed=0):
    """Oscillating series: both long and short Donchian breakouts fire."""

    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        phase = (t // 30) % 2
        px = max(1.0, px + (0.6 if phase == 0 else -0.6) + rng.uniform(-0.1, 0.1))
        out.append(Candle(t * 14_400_000, px, px + 0.5, px - 0.5, px, 10.0))
    return out


class Baseline1Test(unittest.TestCase):
    def test_sides_strictly_alternate(self):
        trades = donchian_reverse(_osc(300), n=20, cost=CostModel())
        self.assertTrue(trades)
        for a, b in zip(trades, trades[1:]):
            self.assertEqual(a.side, -b.side)
        for t in trades:
            self.assertIn(t.side, (-1, 1))

    def test_entry_is_next_bar_open(self):
        candles = _osc(300)
        trades = donchian_reverse(candles, n=20, cost=CostModel())
        t = trades[0]
        self.assertEqual(t.entry_px, candles[t.entry_index].open)

    def test_trades_are_causal(self):
        candles = _osc(300)
        base = donchian_reverse(candles, n=20, cost=CostModel())
        candles[280] = Candle(candles[280].timestamp_ms, 9e9, 9e9, 9e9, 9e9, 9e9)
        extended = candles + _osc(40, seed=1)
        after = donchian_reverse(extended, n=20, cost=CostModel())
        base_pre = [t for t in base if t.exit_index < 280]
        after_pre = [t for t in after if t.exit_index < 280]
        self.assertEqual(base_pre, after_pre)


if __name__ == "__main__":
    unittest.main()
