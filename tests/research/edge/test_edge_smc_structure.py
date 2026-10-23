from __future__ import annotations

import unittest

from moonface.core.models import Candle
from moonface.research.edge._smc import (
    classify_structure,
    detect_choch,
)


def candle(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(
        timestamp_ms=1780275600000 + index * 3_600_000,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


class ClassifyStructureTest(unittest.TestCase):
    def _rising(self) -> list[Candle]:
        # n_periods=1: last two swing highs rising, last two swing lows rising.
        # Swing highs: idx1=12, idx3=14, idx6=16 (rising)
        # Swing lows: idx2=7, idx7=11 (7→11 = higher)
        return [
            candle(0, 10, 11, 9, 10),
            candle(1, 10, 12, 8, 11),    # swing high 12
            candle(2, 11, 11, 7, 8),     # swing low 7
            candle(3, 8, 14, 8, 13),     # swing high 14 (higher)
            candle(4, 13, 13, 9, 10),
            candle(5, 10, 15, 10, 14),
            candle(6, 14, 16, 13, 15),   # swing high 16 (higher)
            candle(7, 15, 15, 11, 12),   # swing low 11 (higher)
            candle(8, 12, 14, 12, 13),
        ]

    def test_higher_highs_and_lows_are_bullish(self) -> None:
        state = classify_structure(self._rising(), n_periods=1)
        self.assertEqual(state.trend, "BULLISH")

    def test_lower_highs_and_lows_are_bearish(self) -> None:
        # Thin candles alternating peaks/troughs, both descending.
        # Highs: 110, 100, 90 (lower). Lows: 85, 70 (lower).
        falling = [
            candle(0, 100, 101,  99, 100),
            candle(1, 109, 110, 109, 109.5),  # peak high=110
            candle(2,  86,  86,  85, 85.5),   # trough low=85
            candle(3,  99, 100,  99, 99.5),   # peak high=100 (lower)
            candle(4,  71,  71,  70, 70.5),   # trough low=70 (lower)
            candle(5,  89,  90,  89, 89.5),   # peak high=90 (lower)
            candle(6,  56,  56,  55, 55.5),   # trough low=55 (lower)
            candle(7,  55,  56,  54, 55),
        ]
        state = classify_structure(falling, n_periods=1)
        self.assertEqual(state.trend, "BEARISH")

    def test_mixed_structure_is_neutral(self) -> None:
        # 6 candles, n_periods=1, swing indices [1..4]
        # Highs: idx1=20, idx3=18 (lower). Lows: idx2=3, idx4=6 (higher). Mixed → NEUTRAL
        candles = [
            candle(0, 10, 15, 5, 10),
            candle(1, 10, 20, 9, 15),   # swing high 20
            candle(2, 15, 16, 3, 5),    # swing low 3
            candle(3, 5, 18, 8, 12),    # swing high 18 (lower), low=8
            candle(4, 12, 13, 6, 8),    # swing low 6 (higher than 3)
            candle(5, 8, 14, 7, 10),    # boundary
        ]
        state = classify_structure(candles, n_periods=1)
        self.assertEqual(state.trend, "NEUTRAL")


class DetectChochTest(unittest.TestCase):
    def test_bullish_choch_requires_break_with_displacement(self) -> None:
        # Swing high at index 1 = 12. A later wide candle closes above 12.
        candles = [
            candle(0, 10, 11, 9, 10),
            candle(1, 10, 12, 8, 11),   # swing high 12 (n_periods=1)
            candle(2, 11, 11, 7, 8),    # swing low 7
            candle(3, 8, 9, 7, 8),
            candle(4, 8, 16, 8, 15),    # wide range 8 closes above 12 -> displacement
        ]
        event = detect_choch(
            candles,
            direction="BULLISH",
            start_index=2,
            atr_value=2.0,
            displacement_mult=1.5,
            n_periods=1,
        )
        assert event is not None
        self.assertEqual(event.kind, "CHOCH")
        self.assertEqual(event.direction, "BULLISH")
        self.assertEqual(event.index, 4)

    def test_no_choch_without_displacement(self) -> None:
        candles = [
            candle(0, 10, 11, 9, 10),
            candle(1, 10, 12, 8, 11),
            candle(2, 11, 11, 7, 8),
            candle(3, 8, 9, 7, 8),
            candle(4, 8, 13, 12, 12.5),  # closes above 12 but range only 1 < 1.5*atr
        ]
        event = detect_choch(
            candles,
            direction="BULLISH",
            start_index=2,
            atr_value=2.0,
            displacement_mult=1.5,
            n_periods=1,
        )
        self.assertIsNone(event)
