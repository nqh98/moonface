from __future__ import annotations

import unittest

from moonface.research.edge.pivots import PivotCtx, daily_pivots
from moonface.core.models import Candle

_HOUR = 3_600_000
_DAY = 86_400_000


class DailyPivotsTest(unittest.TestCase):
    def _two_day_series(self) -> list[Candle]:
        # Day 0: H=120, L=90, C=105 (close = last bar of the day).
        day0 = [
            Candle(0 * _HOUR, 100, 110, 90, 100, 1.0),
            Candle(1 * _HOUR, 105, 120, 95, 105, 1.0),
        ]
        # Day 1: one bar, OHLC irrelevant to its own pivot.
        day1 = [Candle(_DAY, 130, 140, 125, 135, 1.0)]
        return day0 + day1

    def test_traditional_levels_from_prior_day(self) -> None:
        pivots = daily_pivots(self._two_day_series())
        ctx = pivots[2]  # day-1 bar
        assert ctx is not None
        # P=(120+90+105)/3=105; R1=2P-L=120; S1=2P-H=90; R2=P+(H-L)=135;
        # S2=P-(H-L)=75; R3=H+2(P-L)=150; S3=L-2(H-P)=60.
        self.assertEqual(ctx, PivotCtx(p=105.0, r1=120.0, s1=90.0, r2=135.0,
                                       s2=75.0, r3=150.0, s3=60.0))

    def test_first_day_bars_are_none(self) -> None:
        pivots = daily_pivots(self._two_day_series())
        self.assertIsNone(pivots[0])
        self.assertIsNone(pivots[1])

    def test_no_lookahead_pivot_ignores_same_day_future(self) -> None:
        series = self._two_day_series()
        baseline = daily_pivots(series)[2]
        series[2] = Candle(_DAY, 130, 999, 125, 135, 1.0)
        self.assertEqual(daily_pivots(series)[2], baseline)

    def test_length_matches_input(self) -> None:
        series = self._two_day_series()
        self.assertEqual(len(daily_pivots(series)), len(series))
