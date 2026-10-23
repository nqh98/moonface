from __future__ import annotations

import unittest

from moonface.core.indicators import roc, rsi, sma


class IndicatorTest(unittest.TestCase):
    def test_sma_last_n(self) -> None:
        self.assertAlmostEqual(sma([1, 2, 3, 4, 5], 3), 4.0)  # mean of [3,4,5]

    def test_roc_fractional_change(self) -> None:
        self.assertAlmostEqual(roc([100, 110], 1), 0.1)        # (110-100)/100
        self.assertEqual(roc([100], 5), 0.0)                   # too short -> 0

    def test_rsi_all_gains_is_100(self) -> None:
        closes = [float(i) for i in range(1, 20)]              # strictly rising
        self.assertEqual(rsi(closes, 14), 100.0)

    def test_rsi_neutral_when_too_short(self) -> None:
        self.assertEqual(rsi([1.0, 2.0], 14), 50.0)