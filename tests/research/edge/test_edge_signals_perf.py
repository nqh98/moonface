"""Performance + behavior-preservation tests for the price signal generators.

These generators historically recomputed their indicator over a *growing full
prefix* every bar (`rsi/sma/atr/roc(closes[:i+1], ...)` and
`classify_structure(h1[:i+1], ...)`), which is O(n^2). With TF-dispatch moving
configs to native 1h/2h, that turned "slow" into "hangs" (a single
`reversion_in_range` config is ~85s on 4h, ~22 min on 1h) and made the
consolidated leaderboard practically irreproducible.

The fix bounds each indicator call to the window it actually reads (the helpers
are tail-bounded) and precomputes the structure-trend series once. These tests
guard BOTH:
  * perf      -- a 6000-bar run finishes in well under the O(n^2) cost, and
  * behavior  -- the bounded/precomputed output is byte-identical to the legacy
                 full-prefix output (golden master, captured pre-fix).

Deterministic synthetic series (seeded) so the golden fixture is reproducible
without depending on the gitignored price cache.
"""
from __future__ import annotations

import json
import random
import time
import unittest
from pathlib import Path

from moonface.core.models import Candle
from moonface.research.edge.signals import (atr_channel_break, ma_cross,
                                            price_vs_ma, reversion_in_range,
                                            roc_sign)
from moonface.research.edge.system_signals import (trend_pullback,
                                                   vol_compression_breakout)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "edge_signals_perf_golden.json"


def _synth(n: int, seed: int) -> list[Candle]:
    """Deterministic pseudo-price walk with varying spread (realistic ATR/RSI)."""
    rnd = random.Random(seed)
    ts0 = 1_577_836_800_000
    out: list[Candle] = []
    price = 100.0
    for i in range(n):
        step = rnd.gauss(0.0, 1.5)
        price = max(1.0, price + step)
        spread = 0.5 + rnd.random() * 2.0
        high = price + spread
        low = max(0.1, price - spread)
        open_ = price - step * 0.5
        out.append(Candle(ts0 + i * 3_600_000, open_, high, low, price, 1.0))
    return out


# (label, generator, params). Covers every generator whose per-bar indicator
# call was a full-prefix slice (the O(n^2) offenders).
CASES = [
    ("ma_cross", ma_cross, {"fast": 10, "slow": 50}),
    ("ma_cross_slow", ma_cross, {"fast": 50, "slow": 200}),
    ("price_vs_ma", price_vs_ma, {"period": 100}),
    ("roc_sign", roc_sign, {"period": 24}),
    ("atr_channel_break", atr_channel_break, {"k": 1.5, "atr_period": 14}),
    ("reversion_in_range", reversion_in_range, {"period": 14, "low": 30, "high": 70}),
    ("reversion_in_range_wide", reversion_in_range, {"period": 14, "low": 20, "high": 80}),
    ("vol_compression_breakout", vol_compression_breakout,
     {"squeeze_n": 20, "atr_period": 14, "k": 1.0}),
    ("trend_pullback", trend_pullback, {"ma": 50, "pull_atr": 1.5, "atr_period": 14}),
]


class BehaviorPreservationTest(unittest.TestCase):
    """Bounded/precomputed generators must reproduce the legacy full-prefix
    output exactly (golden master captured before the fix)."""

    def test_matches_golden_master(self) -> None:
        self.assertTrue(FIXTURE.exists(),
                        f"missing golden fixture {FIXTURE}; regenerate via "
                        f"tools/edge/_gen_edge_signals_golden.py")
        golden = json.loads(FIXTURE.read_text())
        for series_tag, n, seed in [("A", 2000, 20260630), ("B", 1500, 7)]:
            h1 = _synth(n, seed)
            for label, gen, params in CASES:
                key = f"{series_tag}|{label}"
                self.assertIn(key, golden, f"no golden entry for {key}")
                got = gen(h1, params)
                self.assertEqual(got, [tuple(e) for e in golden[key]],
                                 f"{label} diverged from golden on series {series_tag}")


class PerfRegressionTest(unittest.TestCase):
    """A 6000-bar run must finish well under the legacy O(n^2) cost. The legacy
    full-prefix `reversion_in_range` takes ~15s here (and ~22 *minutes* on a
    57k-bar 1h series); the bounded version is sub-second."""

    def test_reversion_in_range_under_five_seconds(self) -> None:
        h1 = _synth(6000, 4242)
        t0 = time.monotonic()
        reversion_in_range(h1, {"period": 14, "low": 30, "high": 70})
        dt = time.monotonic() - t0
        self.assertLess(dt, 5.0,
                        f"reversion_in_range took {dt:.1f}s on 6000 bars -- "
                        f"O(n^2) prefix-recompute regressed")

    def test_atr_channel_break_under_five_seconds(self) -> None:
        h1 = _synth(6000, 4242)
        t0 = time.monotonic()
        atr_channel_break(h1, {"k": 1.5, "atr_period": 14})
        dt = time.monotonic() - t0
        self.assertLess(dt, 5.0,
                        f"atr_channel_break took {dt:.1f}s on 6000 bars -- "
                        f"O(n^2) prefix-recompute regressed")


if __name__ == "__main__":
    unittest.main()
