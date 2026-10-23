from __future__ import annotations

import unittest

from moonface.research.edge.signals import REGISTRY, atr_channel_break, donchian_break, ma_cross, price_vs_ma, reversion_in_range, roc_sign, smc_continuation
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def series(closes: list[float]) -> list[Candle]:
    return [Candle(1780275600000 + i * 3_600_000, c, c + 1, c - 1, c, 1.0)
            for i, c in enumerate(closes)]


class TrendSignalTest(unittest.TestCase):
    def test_ma_cross_emits_long_on_golden_cross(self) -> None:
        # Down then up so the fast SMA crosses above the slow SMA.
        closes = [10, 9, 8, 7, 6, 5, 6, 8, 11, 15, 20, 26]
        out = ma_cross(series(closes), {"fast": 2, "slow": 4})
        self.assertTrue(any(side == "LONG" for _, side in out))
        # No entry is ever emitted on the final bar.
        self.assertTrue(all(i < len(closes) - 1 for i, _ in out))

    def test_price_vs_ma_long_when_price_crosses_above(self) -> None:
        closes = [10, 10, 10, 10, 9, 9, 12, 13]
        out = price_vs_ma(series(closes), {"period": 3})
        self.assertTrue(any(side == "LONG" for _, side in out))

    def test_roc_sign_flips_to_long(self) -> None:
        closes = [10, 9, 8, 7, 9, 11, 13]
        out = roc_sign(series(closes), {"period": 2})
        self.assertTrue(any(side == "LONG" for _, side in out))


class BreakoutSignalTest(unittest.TestCase):
    def test_donchian_long_on_new_high(self) -> None:
        closes = [10] * 25 + [50, 50]  # penultimate bar breaks the 20-bar high
        out = donchian_break(series(closes), {"n": 20})
        self.assertIn((25, "LONG"), out)

    def test_donchian_short_on_new_low(self) -> None:
        closes = [50] * 25 + [10, 10]
        out = donchian_break(series(closes), {"n": 20})
        self.assertIn((25, "SHORT"), out)

    def test_donchian_long_only_suppresses_shorts(self) -> None:
        # The deployable Slice-2 swing is long-only: a downside break must not
        # emit a SHORT entry when long_only is set.
        closes = [50] * 25 + [10, 10]
        out = donchian_break(series(closes), {"n": 20, "long_only": True})
        self.assertFalse(any(side == "SHORT" for _, side in out))

    def test_donchian_long_only_keeps_longs(self) -> None:
        closes = [10] * 25 + [50, 50]
        out = donchian_break(series(closes), {"n": 20, "long_only": True})
        self.assertIn((25, "LONG"), out)

    def test_atr_channel_long_on_expansion(self) -> None:
        closes = [100] * 20 + [130, 130]  # extra bar so breakout is on bar 20, not the last
        out = atr_channel_break(series(closes), {"k": 1.0, "atr_period": 14})
        self.assertTrue(any(side == "LONG" for _, side in out))


class SmcContinuationTest(unittest.TestCase):
    def test_returns_entries_with_valid_sides(self) -> None:
        # A sweep-down-then-rally shape; we only assert structural validity, not a
        # specific index (detector internals are exercised by their own tests).
        closes = ([100] * 30 + [92, 90, 96, 104, 112, 120]
                  + [118, 122, 119, 124] * 5)
        h1 = series(closes)
        out = smc_continuation(h1, {"lookback": 30})
        self.assertTrue(all(side in ("LONG", "SHORT") for _, side in out))
        self.assertTrue(all(0 <= i < len(h1) - 1 for i, _ in out))

    def test_ignores_history_beyond_window_cap(self) -> None:
        # The production advisor only ever sees the last 100 H1 bars (runner.H1_WINDOW_CAP).
        # smc_continuation must mirror that: prepending inert ancient history must not
        # change which entries fire (only shift their absolute indices by the offset).
        active = ([100] * 30 + [92, 90, 96, 104, 112, 120]
                  + [118, 122, 119, 124] * 5)
        # A structured ancient prefix (a wide saw-tooth) that, if the detectors saw it,
        # would create extra pools/swings and change the result.
        prefix = [80, 140, 70, 150, 60, 160] * 4
        offset = 500  # > H1_WINDOW_CAP (100), so the extra bars must be ignored
        short = series([float(c) for c in prefix + active])
        long = series([float(c) for c in ([90.0] * offset) + prefix + active])
        out_short = smc_continuation(short, {"lookback": 30})
        out_long = smc_continuation(long, {"lookback": 30})
        shifted = [(i - offset, side) for i, side in out_long]
        self.assertEqual(shifted, out_short)


class ReversionSignalTest(unittest.TestCase):
    def test_only_emits_in_neutral_regime(self) -> None:
        # Higher-highs / higher-lows pattern => classify_structure is BULLISH,
        # so a regime-gated reversion signal must emit nothing.
        closes: list[float] = []
        for cycle in range(6):
            for j in range(5):
                closes.append(100 + cycle * 5 + j * 3)
            closes.append(120 + cycle * 10)  # peak
            for j in range(5):
                closes.append(120 + cycle * 10 - (j + 1) * 3)
            closes.append(100 + cycle * 5)  # valley
            closes.append(100 + cycle * 5 + 1.5)
        out = reversion_in_range(series(closes),
                                 {"period": 14, "low": 30, "high": 70})
        self.assertEqual(out, [])

    def test_returns_valid_sides_only(self) -> None:
        # Bounded range (80-120) with sustained declines and sharp rallies.
        # classify_structure stays NEUTRAL but RSI reaches oversold levels.
        closes: list[float] = []
        for cycle in range(6):
            for j in range(12):
                closes.append(120 - j * (40 / 12))
            closes.extend([85, 100, 115, 120])
        out = reversion_in_range(series(closes),
                                 {"period": 14, "low": 35, "high": 65})
        self.assertTrue(all(side in ("LONG", "SHORT") for _, side in out))


class RegistryTest(unittest.TestCase):
    def test_registry_covers_all_families(self) -> None:
        self.assertEqual(
            set(REGISTRY),
            {"ma_cross", "price_vs_ma", "roc_sign", "donchian_break",
             "atr_channel_break", "smc_continuation", "reversion_in_range",
             "atr_channel_break|pivot_bias", "atr_channel_break|pivot_proximity",
             "atr_channel_break|pivot_levelbreak", "donchian_break|pivot_bias",
             "donchian_break|pivot_proximity", "donchian_break|pivot_levelbreak"},
        )

    def test_every_signal_runs_and_respects_no_lookahead(self) -> None:
        # Assert no entry index reaches the final bar (the only place a one-pass
        # generator could leak future data through an evaluator).
        closes = [100 + (i % 7) - 3 for i in range(200)]
        h1 = series([float(c) for c in closes])
        for name, (generator, grid) in REGISTRY.items():
            for params in grid:
                out = generator(h1, params)
                self.assertTrue(all(0 <= i < len(h1) - 1 for i, _ in out),
                                f"{name} {params} emitted an out-of-range index")
                self.assertTrue(all(s in ("LONG", "SHORT") for _, s in out),
                                f"{name} {params} emitted a bad side")


class WithFilterTest(unittest.TestCase):
    def test_filtered_entries_are_subset_of_base(self) -> None:
        from moonface.research.edge.signals import donchian_break, with_filter
        from moonface.research.edge.filters import pivot_bias
        gen = with_filter(donchian_break, pivot_bias)
        closes = [10] * 25 + [50] * 60 + [5] * 60  # produces both break sides
        h1 = series(closes)
        params = {"base": {"n": 100}, "filter": {}}
        # Build a tiny base to compare against using the same base params:
        base_out = donchian_break(h1, {"n": 100})
        filt_out = gen(h1, params)
        self.assertTrue(set(filt_out).issubset(set(base_out)))

    def test_registry_has_eight_filtered_rows(self) -> None:
        from moonface.research.edge.signals import REGISTRY
        keys = [k for k in REGISTRY if "|" in k]
        self.assertEqual(sorted(keys), sorted([
            "atr_channel_break|pivot_bias",
            "atr_channel_break|pivot_proximity",
            "atr_channel_break|pivot_levelbreak",
            "donchian_break|pivot_bias",
            "donchian_break|pivot_proximity",
            "donchian_break|pivot_levelbreak",
        ]))
        # proximity carries a 2-point grid; bias/levelbreak a single combo.
        self.assertEqual(len(REGISTRY["atr_channel_break|pivot_proximity"][1]), 2)
        self.assertEqual(len(REGISTRY["donchian_break|pivot_bias"][1]), 1)

    def test_filtered_grid_records_base_and_filter_params(self) -> None:
        from moonface.research.edge.signals import REGISTRY
        _, grid = REGISTRY["atr_channel_break|pivot_proximity"]
        self.assertEqual(grid[0]["base"], {"k": 2.0, "atr_period": 14})
        self.assertEqual(grid[0]["filter"], {"x": 0.25, "atr_period": 14})
