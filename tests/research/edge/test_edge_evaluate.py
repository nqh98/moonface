from __future__ import annotations

import unittest

from moonface.research.edge.evaluate import bracket_r, horizon_r
from moonface.core.models import Candle


def candle(i: int, o: float, h: float, lo: float, c: float) -> Candle:
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


class HorizonTest(unittest.TestCase):
    def test_long_gain_is_positive_r(self) -> None:
        # Flat history to fix ATR, then price rises. risk = k*ATR.
        h1 = [candle(i, 100, 101, 99, 100) for i in range(20)]
        h1 += [candle(20, 100, 106, 100, 105)]
        # Entry at i=19 (close 100); 1 bar later close is 105 => +5 move.
        r = horizon_r(19, "LONG", h1, k=1.0, atr_period=14, n_bars=1)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0.0)

    def test_short_sign_inverts(self) -> None:
        h1 = [candle(i, 100, 101, 99, 100) for i in range(20)]
        h1 += [candle(20, 100, 101, 94, 95)]
        r_long = horizon_r(19, "LONG", h1, k=1.0, atr_period=14, n_bars=1)
        r_short = horizon_r(19, "SHORT", h1, k=1.0, atr_period=14, n_bars=1)
        self.assertAlmostEqual(r_long, -r_short)


class BracketTest(unittest.TestCase):
    def test_long_hits_take_profit(self) -> None:
        h1 = [candle(i, 100, 101, 99, 100) for i in range(20)]
        # Future bar opens at 100 and rallies through TP (= entry + 2*ATR).
        h1 += [candle(20, 100, 130, 100, 128)]
        r = bracket_r(19, "LONG", h1, k=1.0, m=2.0, atr_period=14,
                      fee_rate=0.0, slippage=0.0)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0.0)

    def test_none_when_no_future_bars(self) -> None:
        h1 = [candle(i, 100, 101, 99, 100) for i in range(20)]
        self.assertIsNone(bracket_r(19, "LONG", h1, k=1.0, m=2.0, atr_period=14,
                                    fee_rate=0.0, slippage=0.0))
