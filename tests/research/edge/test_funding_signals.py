from __future__ import annotations

import unittest

from moonface.core.models import Candle


def _candles(n: int) -> list[Candle]:
    return [Candle(timestamp_ms=i, open=1.0, high=1.0, low=1.0, close=1.0,
                   volume=0.0) for i in range(n)]


class FundingFadeTest(unittest.TestCase):
    def test_rising_funding_shorts_once_edge_triggered(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_fade
        funding = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]  # last is always the outlier
        gen = make_funding_fade(funding)
        entries = gen(_candles(6), {"window": 3, "z_thr": 1.0})
        # z>=1 from i=2 onward, side stays SHORT -> exactly one entry at i=2
        self.assertEqual(entries, [(2, "SHORT")])

    def test_falling_funding_longs(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_fade
        funding = [0.0, -1.0, -2.0, -3.0]
        gen = make_funding_fade(funding)
        entries = gen(_candles(4), {"window": 3, "z_thr": 1.0})
        self.assertEqual(entries[0], (2, "LONG"))

    def test_none_window_skipped(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_fade
        funding = [None, 1.0, 2.0]
        gen = make_funding_fade(funding)
        self.assertEqual(gen(_candles(3), {"window": 3, "z_thr": 1.0}), [])


class FundingConfirmTest(unittest.TestCase):
    def test_persistent_positive_longs_once(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_confirm
        funding = [0.001, 0.001, 0.001, 0.001]
        gen = make_funding_confirm(funding)
        entries = gen(_candles(4), {"persist": 3, "lvl": 0.0005})
        self.assertEqual(entries, [(2, "LONG")])

    def test_persistent_negative_shorts(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_confirm
        funding = [-0.001, -0.001, -0.001]
        gen = make_funding_confirm(funding)
        entries = gen(_candles(3), {"persist": 3, "lvl": 0.0005})
        self.assertEqual(entries, [(2, "SHORT")])

    def test_below_level_no_entry(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_confirm
        funding = [0.0001, 0.0001, 0.0001]
        gen = make_funding_confirm(funding)
        self.assertEqual(gen(_candles(3), {"persist": 3, "lvl": 0.0005}), [])

    def test_mixed_sign_no_entry(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_confirm
        funding = [0.001, -0.001, 0.001]
        gen = make_funding_confirm(funding)
        self.assertEqual(gen(_candles(3), {"persist": 3, "lvl": 0.0005}), [])


class FundingFlipTest(unittest.TestCase):
    def test_cross_up_longs(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_flip
        funding = [-0.01, 0.01]
        gen = make_funding_flip(funding)
        self.assertEqual(gen(_candles(2), {"debounce": 2}), [(1, "LONG")])

    def test_cross_down_shorts(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_flip
        funding = [0.01, -0.01]
        gen = make_funding_flip(funding)
        self.assertEqual(gen(_candles(2), {"debounce": 2}), [(1, "SHORT")])

    def test_debounce_suppresses_quick_reflip(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_flip
        funding = [-1.0, 1.0, -1.0, 1.0]  # flips every bar
        gen = make_funding_flip(funding)
        # i=1 LONG fires; i=2 SHORT within debounce window suppressed; i=3 LONG fires
        self.assertEqual(gen(_candles(4), {"debounce": 2}), [(1, "LONG"), (3, "LONG")])

    def test_none_gap_skipped(self) -> None:
        from moonface.research.edge.funding_signals import make_funding_flip
        funding = [None, 0.01]
        gen = make_funding_flip(funding)
        self.assertEqual(gen(_candles(2), {"debounce": 2}), [])