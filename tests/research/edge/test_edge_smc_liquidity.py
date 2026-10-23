from __future__ import annotations

import unittest

from moonface.research.edge._smc import detect_liquidity, detect_sweeps
from moonface.core.models import Candle


def candle(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(
        timestamp_ms=1780275600000 + index * 3_600_000,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


class LiquidityToleranceTest(unittest.TestCase):
    def test_equal_highs_form_buy_side_pool(self) -> None:
        candles = [
            candle(0, 100, 110, 95, 105),
            candle(1, 105, 110.2, 100, 106),
            candle(2, 106, 108, 101, 102),
        ]
        # tolerance = 0.5 absolute => the two ~110 highs match.
        ctx = detect_liquidity(candles, tolerance=0.5)
        self.assertTrue(any(pool.side == "BUY" for pool in ctx.pools))

    def test_scale_relative_tolerance_matches_large_prices(self) -> None:
        candles = [
            candle(0, 100000, 100100, 99000, 100050),
            candle(1, 100050, 100120, 99500, 100060),  # high within 20 of first
            candle(2, 100060, 100080, 99600, 99700),
        ]
        # absolute tol 0.5 would never match; 0.05% of 100100 = ~50 does.
        ctx = detect_liquidity(candles, tolerance=0.05 / 100 * 100100)
        self.assertTrue(any(pool.side == "BUY" for pool in ctx.pools))


class SweepDetectionTest(unittest.TestCase):
    def test_sell_side_sweep_detected(self) -> None:
        # Equal lows ~ 90, then a candle wicks below and closes back above.
        candles = [
            candle(0, 100, 105, 90, 95),
            candle(1, 95, 100, 90.2, 96),    # equal low pool ~90.1
            candle(2, 96, 99, 92, 97),
            candle(3, 97, 98, 85, 96),       # wicks to 85 (below pool), closes 96 (above)
        ]
        pools = detect_liquidity(candles, tolerance=0.5).pools
        sweeps = detect_sweeps(candles, pools)
        self.assertTrue(any(s.side == "SELL" and s.index == 3 for s in sweeps))

    def test_no_sweep_when_close_stays_below_pool(self) -> None:
        candles = [
            candle(0, 100, 105, 90, 95),
            candle(1, 95, 100, 90.2, 96),
            candle(2, 96, 99, 92, 97),
            candle(3, 97, 98, 85, 86),       # closes 86, below the pool -> not a sweep
        ]
        pools = detect_liquidity(candles, tolerance=0.5).pools
        sweeps = detect_sweeps(candles, pools)
        self.assertFalse(any(s.index == 3 for s in sweeps))
