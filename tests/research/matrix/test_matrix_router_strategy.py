import math
import random
import unittest

from moonface.core.models import Candle
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.strategies import donchian_reverse
from moonface.research.matrix.router.semantics import (
    MODE_FREEZE,
    MODE_QUARANTINE,
    MODE_TREND,
)
from moonface.research.matrix.router.strategy import router_conditioned


def _osc(n, seed=0):
    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        phase = (t // 30) % 2
        px = max(1.0, px + (0.6 if phase == 0 else -0.6) + rng.uniform(-0.1, 0.1))
        out.append(Candle(t * 14_400_000, px, px + 0.5, px - 0.5, px, 10.0))
    return out


class RouterStrategyTest(unittest.TestCase):
    def test_all_trend_reduces_to_baseline1(self):
        candles = _osc(300)
        cost = CostModel()
        modes = {i: MODE_TREND for i in range(len(candles))}
        self.assertEqual(
            router_conditioned(candles, modes, n=20, cost=cost),
            donchian_reverse(candles, n=20, cost=cost),
        )

    def test_all_freeze_makes_no_trades(self):
        candles = _osc(300)
        modes = {i: MODE_FREEZE for i in range(len(candles))}
        self.assertEqual(router_conditioned(candles, modes, n=20), [])

    def test_quarantine_is_quarter_size_of_trend(self):
        candles = _osc(300)
        cost = CostModel()
        trend = router_conditioned(
            candles,
            {i: MODE_TREND for i in range(300)},
            n=20,
            cost=cost,
        )
        quar = router_conditioned(
            candles,
            {i: MODE_QUARANTINE for i in range(300)},
            n=20,
            cost=cost,
        )
        self.assertEqual(len(trend), len(quar))
        self.assertTrue(trend)
        for a, b in zip(trend, quar):
            self.assertEqual(a.entry_index, b.entry_index)
            self.assertEqual(a.exit_index, b.exit_index)
            self.assertTrue(
                math.isclose(
                    b.net_return,
                    0.25 * a.net_return,
                    rel_tol=1e-9,
                    abs_tol=1e-12,
                )
            )

    def test_freeze_region_does_not_increase_trades(self):
        candles = _osc(300)
        allt = router_conditioned(
            candles,
            {i: MODE_TREND for i in range(300)},
            n=20,
        )
        half = {i: (MODE_TREND if i < 150 else MODE_FREEZE) for i in range(300)}
        self.assertLessEqual(len(router_conditioned(candles, half, n=20)), len(allt))


if __name__ == "__main__":
    unittest.main()
