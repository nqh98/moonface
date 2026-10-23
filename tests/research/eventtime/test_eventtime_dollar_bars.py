import unittest

from moonface.core.models import Candle
from moonface.research.eventtime.dollar_bars import (
    build_dollar_bars,
    calibrate_bar_size,
    rolling_dollar_volume,
)
from moonface.research.eventtime.vision_klines import MinuteBar


class TestRollingDollarVolume(unittest.TestCase):
    def test_returns_trailing_full_window_sums(self):
        minutes = [
            MinuteBar(0, 1.0, 1.0, 1.0, 1.0, 1.0, 10.0),
            MinuteBar(60_000, 1.0, 1.0, 1.0, 1.0, 1.0, 20.0),
            MinuteBar(120_000, 1.0, 1.0, 1.0, 1.0, 1.0, 30.0),
        ]

        self.assertEqual(rolling_dollar_volume(minutes, window_min=2), [30.0, 50.0])


class TestCalibrateBarSize(unittest.TestCase):
    def test_returns_median_rolling_dollar_volume(self):
        minutes = [
            MinuteBar(0, 1.0, 1.0, 1.0, 1.0, 1.0, 10.0),
            MinuteBar(60_000, 1.0, 1.0, 1.0, 1.0, 1.0, 20.0),
            MinuteBar(120_000, 1.0, 1.0, 1.0, 1.0, 1.0, 30.0),
            MinuteBar(180_000, 1.0, 1.0, 1.0, 1.0, 1.0, 40.0),
        ]

        self.assertEqual(
            calibrate_bar_size(minutes, calib_start_ms=0, calib_end_ms=240_000, window_min=2),
            50.0,
        )

    def test_raises_when_no_full_window_exists(self):
        minutes = [
            MinuteBar(0, 1.0, 1.0, 1.0, 1.0, 1.0, 10.0),
            MinuteBar(60_000, 1.0, 1.0, 1.0, 1.0, 1.0, 20.0),
        ]

        with self.assertRaises(ValueError):
            calibrate_bar_size(minutes, calib_start_ms=0, calib_end_ms=120_000, window_min=3)


class TestBuildDollarBars(unittest.TestCase):
    def test_emits_candles_when_threshold_is_hit_and_discards_partial_tail(self):
        minutes = [
            MinuteBar(0, 100.0, 110.0, 90.0, 105.0, 1.25, 4.0),
            MinuteBar(60_000, 106.0, 112.0, 101.0, 111.0, 2.75, 7.0),
            MinuteBar(120_000, 111.0, 113.0, 108.0, 109.0, 0.5, 2.0),
        ]

        self.assertEqual(
            build_dollar_bars(minutes, dollar_threshold=10.0),
            [
                Candle(
                    timestamp_ms=0,
                    open=100.0,
                    high=112.0,
                    low=90.0,
                    close=111.0,
                    volume=4.0,
                )
            ],
        )
