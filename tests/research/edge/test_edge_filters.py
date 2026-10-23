from __future__ import annotations

import unittest

from moonface.research.edge.filters import (
    pivot_bias,
    pivot_levelbreak,
    pivot_proximity,
)
from moonface.research.edge.pivots import PivotCtx
from moonface.core.models import Candle


def _flat(closes: list[float]) -> list[Candle]:
    # high=close+1, low=close-1 -> ATR settles near ~2.
    return [Candle(i * 3_600_000, c, c + 1, c - 1, c, 1.0)
            for i, c in enumerate(closes)]


def _ctx(p: float) -> PivotCtx:
    return PivotCtx(p=p, s1=p - 10, r1=p + 10, s2=p - 20, r2=p + 20,
                    s3=p - 30, r3=p + 30)


class PivotBiasTest(unittest.TestCase):
    def test_keeps_long_above_p_drops_below(self) -> None:
        h1 = _flat([100, 100])
        pivots = [_ctx(90), _ctx(110)]
        entries = [(0, "LONG"), (1, "LONG")]  # close 100: above 90, below 110
        self.assertEqual(pivot_bias(h1, entries, pivots, {}), [(0, "LONG")])

    def test_keeps_short_below_p_drops_above(self) -> None:
        h1 = _flat([100, 100])
        pivots = [_ctx(110), _ctx(90)]
        entries = [(0, "SHORT"), (1, "SHORT")]
        self.assertEqual(pivot_bias(h1, entries, pivots, {}), [(0, "SHORT")])

    def test_drops_none_pivot(self) -> None:
        h1 = _flat([100])
        self.assertEqual(pivot_bias(h1, [(0, "LONG")], [None], {}), [])


class PivotProximityTest(unittest.TestCase):
    def test_keeps_near_level_drops_far(self) -> None:
        h1 = _flat([100] * 20)  # ATR ~ 2
        near = _ctx(100)        # a level sits exactly at close -> distance 0
        far = _ctx(500)         # nearest level 470 away
        params = {"x": 0.5, "atr_period": 14}
        i = 19
        self.assertEqual(pivot_proximity(h1, [(i, "LONG")], _pad(near, i), params),
                         [(i, "LONG")])
        self.assertEqual(pivot_proximity(h1, [(i, "LONG")], _pad(far, i), params), [])

    def test_drops_none_pivot(self) -> None:
        h1 = _flat([100] * 20)
        params = {"x": 0.5, "atr_period": 14}
        self.assertEqual(pivot_proximity(h1, [(19, "LONG")], [None] * 20, params), [])


class PivotLevelBreakTest(unittest.TestCase):
    def test_long_kept_when_bar_clears_level_upward(self) -> None:
        h1 = _flat([99, 101])          # prev close 99, this close 101
        pivots = [_ctx(90), _ctx(90)]  # p=90 -> r1=100 lies in (99, 101]
        self.assertEqual(pivot_levelbreak(h1, [(1, "LONG")], pivots, {}),
                         [(1, "LONG")])

    def test_long_dropped_when_no_level_crossed(self) -> None:
        h1 = _flat([99, 99.5])        # no level in (99, 99.5]
        pivots = [_ctx(90), _ctx(90)]  # nearest levels 90 and 100
        self.assertEqual(pivot_levelbreak(h1, [(1, "LONG")], pivots, {}), [])

    def test_short_kept_when_bar_clears_level_downward(self) -> None:
        h1 = _flat([101, 99])
        pivots = [_ctx(90), _ctx(90)]  # r1=100 in [99, 101)
        self.assertEqual(pivot_levelbreak(h1, [(1, "SHORT")], pivots, {}),
                         [(1, "SHORT")])


def _pad(ctx, i):
    out = [None] * (i + 1)
    out[i] = ctx
    return out


if __name__ == "__main__":
    unittest.main()
