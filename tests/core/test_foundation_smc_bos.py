from __future__ import annotations

import unittest

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.core.smc import detect_bos


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


class DetectBosTest(unittest.TestCase):
    def test_bullish_bos_breaks_prior_swing_high(self):
        # Rising series: a clear swing high at index 4 (high 120), pullback,
        # then a wide candle at index 9 closing above 120.
        candles = [
            _c(0, 100, 110, 95, 105),
            _c(1, 105, 115, 100, 112),
            _c(2, 112, 118, 108, 110),
            _c(3, 110, 116, 105, 108),
            _c(4, 108, 120, 107, 119),   # swing high 120 (peaks above neighbors)
            _c(5, 119, 121, 112, 114),
            _c(6, 114, 117, 108, 110),
            _c(7, 110, 113, 104, 106),
            _c(8, 106, 112, 105, 111),
            _c(9, 111, 130, 110, 128),   # wide candle, close 128 > 120 -> BOS @9
        ]
        a = atr(candles, 14)
        ev = detect_bos(candles, "BULLISH", start_index=8, atr_value=a,
                        displacement_mult=1.5, n_periods=3)
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.kind, "BOS")
        self.assertEqual(ev.direction, "BULLISH")
        self.assertEqual(ev.index, 9)

    def test_bearish_bos_breaks_prior_swing_low(self):
        # Falling series (mirror of the bullish case): a clear swing low at
        # index 5 (low 79), rally, then a wide candle at index 9 closing below 79.
        candles = [
            _c(0, 100, 105, 90, 95),
            _c(1, 95, 100, 85, 88),
            _c(2, 88, 92, 82, 90),
            _c(3, 90, 95, 84, 92),
            _c(4, 92, 93, 80, 81),
            _c(5, 81, 88, 79, 86),   # swing low 79
            _c(6, 86, 92, 83, 90),
            _c(7, 90, 96, 87, 94),
            _c(8, 94, 95, 88, 89),
            _c(9, 89, 90, 70, 72),   # wide candle, close 72 < 79 -> BOS @9
        ]
        a = atr(candles, 14)
        ev = detect_bos(candles, "BEARISH", start_index=8, atr_value=a,
                        displacement_mult=1.5, n_periods=3)
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.kind, "BOS")
        self.assertEqual(ev.direction, "BEARISH")
        self.assertEqual(ev.index, 9)

    def test_no_bos_when_close_does_not_break_swing(self):
        candles = [_c(i, 100, 105, 95, 100) for i in range(12)]
        self.assertIsNone(detect_bos(candles, "BULLISH", 8, atr(candles, 14), 1.5, 3))

    def test_returns_none_when_atr_nonpositive(self):
        self.assertIsNone(detect_bos([_c(0, 1, 1, 1, 1)], "BULLISH", 0, 0.0, 1.5, 3))
