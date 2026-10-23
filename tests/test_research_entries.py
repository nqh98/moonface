import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.entries import (UnknownEntryFamily, generate_entries,
                                       known_families)
from moonface.kernel.synth import make_candles


class TestGenerateEntries(unittest.TestCase):
    def setUp(self):
        self.candles = make_candles(400, seed=7, drift=0.003, noise=0.01)
        self.bundle = DataBundle(candles=self.candles)

    def test_price_family_resolves(self):
        entries = generate_entries("donchian_break", {"n": 20}, self.bundle)
        self.assertGreater(len(entries), 0)
        for i, side in entries:
            self.assertIn(side, ("LONG", "SHORT"))
            self.assertIsInstance(i, int)

    def test_funding_family_needs_funding(self):
        with self.assertRaises(ValueError):
            generate_entries("funding_flip", {"debounce": 6}, self.bundle)

    def test_funding_flip_emits_on_sign_change(self):
        funding = [-0.0001] + [0.0001] * (len(self.candles) - 1)
        bundle = DataBundle(candles=self.candles, funding=funding)
        entries = generate_entries("funding_flip", {"debounce": 6}, bundle)
        self.assertEqual(entries, [(1, "LONG")])

    def test_basis_family_needs_basis(self):
        with self.assertRaises(ValueError):
            generate_entries("basis_discount_reversion",
                             {"window": 10, "pct": 5}, self.bundle)

    def test_unknown_family_raises(self):
        with self.assertRaises(UnknownEntryFamily):
            generate_entries("nonexistent_signal", {}, self.bundle)


def _flat(n):
    return [Candle(timestamp_ms=i, open=9, high=10, low=8, close=9, volume=100.0)
            for i in range(n)]


class TestForcedErrorDispatch(unittest.TestCase):
    def test_families_registered(self):
        fams = known_families()
        for f in ("failed_breakout_naive", "failed_breakout_harvest",
                  "failed_fade_squeeze", "funding_fade_long"):
            self.assertIn(f, fams)

    def test_failed_fade_squeeze_requires_both_inputs(self):
        b = DataBundle(candles=_flat(50), feature=[1.0] * 50, funding=None)
        with self.assertRaises(ValueError):
            generate_entries("failed_fade_squeeze",
                             {"window": 5, "lookback": 3, "k": 1.0,
                              "funding_pct": 0.2, "funding_window": 10}, b)

    def test_failed_breakout_harvest_dispatches_via_feature(self):
        b = DataBundle(candles=_flat(50), feature=[1.0] * 50)
        out = generate_entries("failed_breakout_harvest",
                               {"donchian_n": 5, "window": 5, "lookback": 3,
                                "k": 1.5, "use_volume": True}, b)
        self.assertIsInstance(out, list)


if __name__ == "__main__":
    unittest.main()
