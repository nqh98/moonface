from __future__ import annotations

import unittest

from moonface.core.models import Candle
from moonface.research.edge.signals import smc_continuation
from moonface.research.edge.smc_variants import (_WINDOW_CAP, choch_only,
                                                  flip, full_reversal,
                                                  structure_bias, sweep_only)

import pytest

pytestmark = pytest.mark.slow


def candle(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(1780275600000 + index * 3_600_000, open_, high, low, close, 1.0)


def reversal_fixture() -> list[Candle]:
    """~140 bars with a repeated, rising sell-sweep -> wide bullish-CHOCH leg so
    the SMC detectors reliably fire. Each 12-bar leg (base B = 100 + 10*leg):
      b4 = swing high (B+15); b8,b9 = equal lows (B-6) -> SELL pool;
      b10 = deep-wick sweep closing back up; b11 = wide rally closing above the
      prior swing high (bullish CHOCH). Detector hyperparams are frozen, so the
      exact firing index is asserted only structurally elsewhere."""
    bars: list[Candle] = []
    idx = 0
    for leg in range(11):
        b = 100 + 10 * leg
        pattern = [
            (b, b + 2, b - 3, b),
            (b + 3, b + 6, b, b + 3),
            (b + 6, b + 9, b + 4, b + 6),
            (b + 9, b + 12, b + 7, b + 9),
            (b + 12, b + 15, b + 10, b + 12),   # swing high B+15
            (b + 10, b + 13, b + 5, b + 10),
            (b + 5, b + 8, b, b + 5),
            (b, b + 3, b - 6, b),               # equal low B-6
            (b - 3, b, b - 6, b - 3),           # equal low B-6 -> SELL pool
            (b - 5, b - 2, b - 20, b - 2),      # sweep: wick B-20, close B-2
            (b - 2, b + 20, b - 4, b + 18),     # wide rally, close > B+15 CHOCH
        ]
        for o, h, lo, c in pattern:
            bars.append(candle(idx, o, h, lo, c))
            idx += 1
    return bars


class FullReversalFlipTest(unittest.TestCase):
    def test_flip_matches_falsified_smc_continuation(self) -> None:
        h1 = reversal_fixture()
        for lookback in (10, 30):
            self.assertEqual(flip(h1, {"lookback": lookback}),
                             smc_continuation(h1, {"lookback": lookback}))

    def test_flip_is_exact_side_inverse_of_full_reversal(self) -> None:
        h1 = reversal_fixture()
        rev = full_reversal(h1, {"lookback": 30})
        flp = flip(h1, {"lookback": 30})
        self.assertEqual([i for i, _ in rev], [i for i, _ in flp])
        self.assertEqual([{"LONG": "SHORT", "SHORT": "LONG"}[s] for _, s in rev],
                         [s for _, s in flp])

    def test_full_reversal_fires_at_least_one_long(self) -> None:
        h1 = reversal_fixture()
        out = full_reversal(h1, {"lookback": 30})
        self.assertTrue(len(out) >= 1)
        self.assertTrue(any(s == "LONG" for _, s in out))

    def test_emitted_indices_and_sides_are_valid(self) -> None:
        h1 = reversal_fixture()
        for gen in (full_reversal, flip):
            out = gen(h1, {"lookback": 30})
            self.assertTrue(all(0 <= i < len(h1) - 1 for i, _ in out))
            self.assertTrue(all(s in ("LONG", "SHORT") for _, s in out))

    def test_flat_window_emits_nothing(self) -> None:
        h1 = [candle(i, 100, 105, 95, 100) for i in range(80)]
        self.assertEqual(full_reversal(h1, {"lookback": 30}), [])
        self.assertEqual(flip(h1, {"lookback": 30}), [])

    def test_window_cap_ignores_ancient_history(self) -> None:
        offset = 500
        active = reversal_fixture()
        long_ = [candle(i, 100, 105, 95, 100) for i in range(offset)] + active
        base = full_reversal(active, {"lookback": 30})
        shifted = [(i - offset, s) for i, s in full_reversal(long_, {"lookback": 30})]
        # Window cap = 100: a bar's decision depends only on the last 100 bars,
        # so events at p >= _WINDOW_CAP see an all-active window in both series
        # and must match. Events at p < _WINDOW_CAP legitimately differ: the
        # prefix still sits inside the 100-bar window, and warmup (_WARMUP=60) is
        # measured from array start, so the bare fixture cannot fire at p < 60
        # while the prefixed series can. (Controller deviation D-T1: the plan's
        # verbatim test asserted all events match, which is false for p < 100.)
        deep_base = [(i, s) for i, s in base if i >= _WINDOW_CAP]
        deep_shifted = [(i, s) for i, s in shifted if i >= _WINDOW_CAP]
        self.assertEqual(deep_shifted, deep_base)


def falling_fixture() -> list[Candle]:
    """Mirror of reversal_fixture with a falling base so structure is BEARISH."""
    bars: list[Candle] = []
    idx = 0
    for leg in range(11):
        b = 300 - 10 * leg  # falling base
        pattern = [
            (b, b + 3, b - 2, b),
            (b - 3, b, b - 5, b - 3),
            (b - 5, b - 2, b - 9, b - 5),
            (b - 9, b - 6, b - 12, b - 9),
            (b - 12, b - 9, b - 15, b - 12),  # swing low B-15
            (b - 10, b - 5, b - 13, b - 10),
            (b - 5, b, b - 8, b - 5),
            (b, b + 6, b, b),                 # equal high B+6
            (b + 3, b + 6, b, b + 3),         # equal high B+6 -> BUY pool
            (b + 5, b + 22, b - 4, b + 2),    # sweep: wick B+22, close B+2
            (b + 2, b - 18, b + 4, b - 16),   # wide drop, close < B-15 CHOCH
        ]
        for o, h, lo, c in pattern:
            bars.append(candle(idx, o, h, lo, c))
            idx += 1
    return bars


class ComponentVariantTest(unittest.TestCase):
    def test_sweep_only_fires_long_after_sell_sweep(self) -> None:
        h1 = reversal_fixture()
        out = sweep_only(h1, {"lookback": 10})
        self.assertTrue(len(out) >= 1)
        self.assertTrue(any(s == "LONG" for _, s in out))
        self.assertTrue(all(s in ("LONG", "SHORT") for _, s in out))

    def test_choch_only_fires_long_on_bullish_choch(self) -> None:
        h1 = reversal_fixture()
        out = choch_only(h1, {})
        self.assertTrue(len(out) >= 1)
        self.assertTrue(any(s == "LONG" for _, s in out))

    def test_structure_bias_long_on_rising_short_on_falling(self) -> None:
        self.assertTrue(any(s == "LONG" for _, s in
                            structure_bias(reversal_fixture(), {"n_periods": 5})))
        self.assertTrue(any(s == "SHORT" for _, s in
                            structure_bias(falling_fixture(), {"n_periods": 5})))

    def test_components_flat_window_empty(self) -> None:
        h1 = [candle(i, 100, 105, 95, 100) for i in range(80)]
        self.assertEqual(sweep_only(h1, {"lookback": 10}), [])
        self.assertEqual(choch_only(h1, {}), [])
        self.assertEqual(structure_bias(h1, {"n_periods": 5}), [])

    def test_components_emit_valid_indices(self) -> None:
        h1 = reversal_fixture()
        for gen, params in ((sweep_only, {"lookback": 10}),
                            (choch_only, {}),
                            (structure_bias, {"n_periods": 5})):
            out = gen(h1, params)
            self.assertTrue(all(0 <= i < len(h1) - 1 for i, _ in out))


if __name__ == "__main__":
    unittest.main()
