# funding_fade_fwd Draft-Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frozen pipeline, run the pre-cutoff dry-run + analysis, and draft D1–D3 for the `funding_fade_fwd` forward program, ending at the human sign-off hard stop.

**Architecture:** One thin frozen runner around the exact code paths that produced the original `positioning_exits` row (`fetch_history`/`FundingCache`, `make_funding_fade`, `EXIT_REGISTRY["fixed_bracket"]`, `exit_r_streams`, `summarize_r`). New code only windows/clamps/orchestrates (core module), resamples completed trade-R streams (analysis module), shuffles funding per-segment (null module), and formats reports (CLI). Design: `docs/research-log/specs/2026-07-13-funding-fade-fwd-design.md`.

**Tech Stack:** Python 3.11+, stdlib only (no numpy). `unittest.TestCase` run via pytest. Determinism via `random.Random(seed)`.

## Global Constraints

- **Data hygiene:** no candle or funding point with `timestamp_ms >= CUTOFF_MS` (2026-06-10T06:51:46Z, the original run's `end_ms`) may enter any frame. The clamp aborts before any summary prints. Accidental exposure → STOP, write a report, await human decision.
- **Frozen identity (verbatim, never edit):** entry `funding_fade {"window": 60, "z_thr": 1.5}`, exit `fixed_bracket {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}`, binance `BTC/USDT:USDT` 4h, funding symbol `BTC/USDT:USDT`, f = 0.01.
- **R definition:** 1R = 1 ATR(14) at entry. A stop hit = −2.0R; a TP hit = +4.0R (verified in `src/moonface/foundation/exits.py::fixed_bracket`).
- **Dry-run tolerance:** exact equality with the archived row at its reported precision (research 254 / +64.7507 / +0.2549 / −32.0; OOS 68 / +76.7285 / +1.1284). Any miss = STOP and ask (spec §5.2); no silent patching.
- Run CLIs as `.venv/bin/python tools/<x>.py` (no bare `python`; `rtk python` is not proxied). Run tests as `.venv/bin/python -m pytest`.
- Git: no AI-attribution trailers; stage, then verify `git diff --cached --stat`, then commit as separate commands (never chain `add && commit`).
- No parameter changes, sweeps, filters, feed integration, or verdicts anywhere in this phase.

---

### Task 1: Core module — frozen identity, clamp, window math, reproduction check

**Files:**
- Create: `src/moonface/research/funding_fade_fwd.py`
- Test: `tests/test_funding_fade_fwd.py`

**Interfaces:**
- Consumes: `fetch_history(exchange, symbol, timeframe, start_ms, end_ms, cache)`, `OhlcvCache(dir)`, `fetch_funding_history(exchange, symbol, start_ms, end_ms, cache)`, `FundingCache(dir)`, `align_funding(candles, points)`, `make_funding_fade(funding)(h1, params)`, `EXIT_REGISTRY["fixed_bracket"]`, `exit_r_streams(h1, entries, exit_fn, exit_params, tail_start)`, `split_research_tail(h1, oos_tail_bars, warmup, future_bars)`, `summarize_r(list[float]) -> Summary`.
- Produces (used by Tasks 2–4):
  - constants `ENTRY_PARAMS`, `EXIT_PARAMS`, `ASSET`, `FRACTION`, `CUTOFF_MS`, `ORIGINAL_START_MS`, `OOS_TAIL_BARS`, `WARMUP`, `FUTURE_BARS`, `ARCHIVED`
  - `class CutoffViolation(RuntimeError)`
  - `assert_pre_cutoff(candles: list[Candle], funding: list[tuple[int, float]]) -> None`
  - `@dataclass(frozen=True) Streams(research: list[tuple[int, float]], tail: list[tuple[int, float]])`
  - `load_pre_cutoff(cache_dir: str) -> tuple[list[Candle], list[float | None]]`
  - `regenerate(perp: list[Candle], funding: list[float | None]) -> Streams`
  - `reproduction_report(streams: Streams) -> tuple[bool, dict]`
  - `identity_hash(dd_budget_r: float, verdict_n_trades: int, verdict_months: int) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funding_fade_fwd.py
import unittest

from moonface.foundation.models import Candle
from moonface.research import funding_fade_fwd as fwd


def _candles(n: int, start_ms: int = 1_600_000_000_000) -> list[Candle]:
    """4h candles trending +0.1/bar with 1.0 range, so ATR(14) == 1.0."""
    out = []
    for i in range(n):
        close = 100.0 + 0.1 * i
        out.append(Candle(timestamp_ms=start_ms + i * 14_400_000,
                          open=close - 0.05, high=close + 0.5,
                          low=close - 0.5, close=close, volume=1.0))
    return out


def _funding_with_spikes(n: int, spikes: list[int]) -> list[float | None]:
    """Alternating ±1e-4 (z==±1, below z_thr 1.5) with +1e-2 spikes (z >> 1.5)."""
    base = [1e-4 if i % 2 == 0 else -1e-4 for i in range(n)]
    for i in spikes:
        base[i] = 1e-2
    return base


class CutoffClampTest(unittest.TestCase):
    def test_rejects_post_cutoff_candle(self):
        good = _candles(3, start_ms=fwd.CUTOFF_MS - 10 * 14_400_000)
        bad = _candles(3, start_ms=fwd.CUTOFF_MS)
        with self.assertRaises(fwd.CutoffViolation):
            fwd.assert_pre_cutoff(good + bad, [])

    def test_rejects_post_cutoff_funding(self):
        with self.assertRaises(fwd.CutoffViolation):
            fwd.assert_pre_cutoff([], [(fwd.CUTOFF_MS, 1e-4)])

    def test_accepts_pre_cutoff(self):
        candles = _candles(3, start_ms=fwd.CUTOFF_MS - 10 * 14_400_000)
        fwd.assert_pre_cutoff(candles, [(fwd.CUTOFF_MS - 1, 1e-4)])  # no raise


class RegenerateTest(unittest.TestCase):
    def test_synthetic_entries_split_and_r_values(self):
        n = 1300  # tail_start = 1300 - 1095 = 205
        candles = _candles(n)
        funding = _funding_with_spikes(n, spikes=[200, 250])
        streams = fwd.regenerate(candles, funding)
        # spike 200 -> research (200 < 205); spike 250 -> tail. SHORT into a
        # rising series stops out at exactly -k_stop = -2.0 R (ATR units).
        self.assertEqual(len(streams.research), 1)
        self.assertEqual(len(streams.tail), 1)
        self.assertEqual(streams.research[0][0], candles[200].timestamp_ms)
        self.assertEqual(streams.research[0][1], -2.0)
        self.assertEqual(streams.tail[0][0], candles[250].timestamp_ms)
        self.assertEqual(streams.tail[0][1], -2.0)

    def test_reproduction_report_mismatch_and_match(self):
        streams = fwd.Streams(research=[(0, 1.0)], tail=[(1, 1.0)])
        ok, got = fwd.reproduction_report(streams)
        self.assertFalse(ok)
        self.assertEqual(got["research_trades"], 1)
        self.assertEqual(set(got), set(fwd.ARCHIVED))


class IdentityHashTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(fwd.identity_hash(-50.0, 123, 12),
                         fwd.identity_hash(-50.0, 123, 12))

    def test_sensitive_to_budget_and_trigger(self):
        base = fwd.identity_hash(-50.0, 123, 12)
        self.assertNotEqual(base, fwd.identity_hash(-40.0, 123, 12))
        self.assertNotEqual(base, fwd.identity_hash(-50.0, 124, 12))

    def test_is_hex_sha256(self):
        h = fwd.identity_hash(-50.0, 123, 12)
        self.assertEqual(len(h), 64)
        int(h, 16)  # parses as hex
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_funding_fade_fwd.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'moonface.research.funding_fade_fwd'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/research/funding_fade_fwd.py
"""funding_fade_fwd — frozen identity, window math, and pre-cutoff loading.

Draft-preparation phase only (design 2026-07-13). Every numeric code path is
the SAME code that produced the original positioning_exits row; this module
only windows, clamps, orchestrates, and hashes. The hard clamp enforces the
data-hygiene rule: nothing at/after the burned-data boundary enters a frame.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from moonface.foundation.data import OhlcvCache, fetch_history
from moonface.foundation.exits import EXIT_REGISTRY
from moonface.foundation.metrics import summarize_r
from moonface.foundation.models import Candle
from moonface.foundation.series import (FundingCache, align_funding,
                                        fetch_funding_history)
from moonface.research.edge.exit_score import exit_r_streams
from moonface.research.edge.funding_signals import make_funding_fade
from moonface.research.sizing import split_research_tail

# Frozen strategy identity — copied verbatim from the original row
# (experiments/positioning_exits/20260610T065146Z, row 2). Never edit.
ENTRY_NAME = "funding_fade"
ENTRY_PARAMS = {"window": 60, "z_thr": 1.5}
EXIT_NAME = "fixed_bracket"
EXIT_PARAMS = {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}
ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
         "timeframe": "4h", "funding_symbol": "BTC/USDT:USDT"}
FRACTION = 0.01  # fixed fractional risk per R, of initial equity

# Original run mechanics (tools/positioning_exit_probe.py defaults at the
# 2026-06-10T06:51:46Z run). CUTOFF_MS is the burned-data boundary AND the
# forward-window start: no gap, no overlap.
CUTOFF_MS = int(datetime(2026, 6, 10, 6, 51, 46,
                         tzinfo=timezone.utc).timestamp() * 1000)
_DAY_MS = 86_400_000
ORIGINAL_YEARS = 3.0
ORIGINAL_START_MS = CUTOFF_MS - int(ORIGINAL_YEARS * 365 * _DAY_MS)
OOS_TAIL_BARS = 1095
WARMUP = 60
FUTURE_BARS = 48

# Archived row values at their reported precision (the dry-run tolerance).
ARCHIVED = {
    "research_trades": 254, "research_net_r": 64.7507,
    "research_expectancy_r": 0.2549, "research_max_dd_r": -32.0,
    "oos_trades": 68, "oos_net_r": 76.7285, "oos_expectancy_r": 1.1284,
}


class CutoffViolation(RuntimeError):
    """Raised before any summary is produced if post-cutoff data is seen."""


def assert_pre_cutoff(candles: list[Candle],
                      funding: list[tuple[int, float]]) -> None:
    """Hard clamp at the data-return boundary (design §3)."""
    bad_c = sum(1 for c in candles if c.timestamp_ms >= CUTOFF_MS)
    bad_f = sum(1 for ts, _ in funding if ts >= CUTOFF_MS)
    if bad_c or bad_f:
        raise CutoffViolation(
            f"post-cutoff data reached the frame: candles={bad_c} "
            f"funding={bad_f} (cutoff_ms={CUTOFF_MS})")


@dataclass(frozen=True)
class Streams:
    research: list[tuple[int, float]]  # ordered (timestamp_ms, r)
    tail: list[tuple[int, float]]


def load_pre_cutoff(cache_dir: str) -> tuple[list[Candle], list[float | None]]:
    """Perp candles + aligned funding for the ORIGINAL window, clamped."""
    perp = fetch_history(ASSET["exchange"], ASSET["symbol"],
                         ASSET["timeframe"], ORIGINAL_START_MS, CUTOFF_MS,
                         OhlcvCache(cache_dir))
    points = fetch_funding_history(ASSET["exchange"], ASSET["funding_symbol"],
                                   ORIGINAL_START_MS, CUTOFF_MS,
                                   FundingCache(cache_dir))
    assert_pre_cutoff(perp, points)
    return perp, align_funding(perp, points)


def regenerate(perp: list[Candle], funding: list[float | None]) -> Streams:
    """Re-run the exact original row through the reused pipeline."""
    entries = make_funding_fade(funding)(perp, ENTRY_PARAMS)
    tail_start = split_research_tail(perp, OOS_TAIL_BARS, WARMUP, FUTURE_BARS)
    exit_fn = EXIT_REGISTRY[EXIT_NAME][0]
    research, tail = exit_r_streams(perp, entries, exit_fn, EXIT_PARAMS,
                                    tail_start)
    return Streams(research=research, tail=tail)


def reproduction_report(streams: Streams) -> tuple[bool, dict]:
    """Compare regenerated summaries with the archived row. A miss is a
    spec §5.2 STOP — callers must not patch around it."""
    rs = summarize_r([r for _, r in streams.research])
    ts = summarize_r([r for _, r in streams.tail])
    got = {
        "research_trades": rs.trade_count, "research_net_r": rs.total_r,
        "research_expectancy_r": rs.expectancy_r,
        "research_max_dd_r": rs.max_drawdown_r,
        "oos_trades": ts.trade_count, "oos_net_r": ts.total_r,
        "oos_expectancy_r": ts.expectancy_r,
    }
    return got == ARCHIVED, got


def identity_hash(dd_budget_r: float, verdict_n_trades: int,
                  verdict_months: int) -> str:
    """sha256 over canonical JSON of rules + all frozen parameters
    (MOE_ORTHO convention). Freezes at human sign-off."""
    payload = {
        "program": "funding_fade_fwd", "version": 1,
        "asset": ASSET,
        "entry": {"family": ENTRY_NAME, "params": ENTRY_PARAMS},
        "exit": {"name": EXIT_NAME, "params": EXIT_PARAMS},
        "fraction": FRACTION,
        "forward_start_ms": CUTOFF_MS,
        "dd_budget_r": dd_budget_r,
        "verdict_trigger": {"later_of": {"n_trades": verdict_n_trades,
                                         "months": verdict_months}},
        "success": {"ci": 0.95, "method": "moving_block_bootstrap",
                    "block": 10, "resamples": 10000, "seed": 42,
                    "rule": "ci_low>0 and cum_r>0"},
        "null_guard": {"runs": 100, "seeds": "0..99",
                       "min_fail_fraction": 0.95},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_funding_fade_fwd.py -v`
Expected: all PASS. If `test_synthetic_entries_split_and_r_values` fails on the r value, STOP — do not adjust the assertion; re-read `fixed_bracket` and the synthetic construction (the frozen exit code is not editable).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/funding_fade_fwd.py tests/test_funding_fade_fwd.py
git diff --cached --stat
git commit -m "feat(funding_fade_fwd): frozen identity, cutoff clamp, reproduction check"
```

---

### Task 2: Analysis module — block bootstrap CI, ruin, TUW, power

**Files:**
- Create: `src/moonface/research/fwd_analysis.py`
- Test: `tests/test_fwd_analysis.py`

**Interfaces:**
- Consumes: nothing project-specific (pure functions over `list[float]` / `list[tuple[int, float]]`).
- Produces (used by Task 4):
  - `moving_block_resample(rs: list[float], rng: random.Random, block: int = 10) -> list[float]`
  - `bootstrap_expectancy_ci(rs, resamples=10_000, block=10, seed=42, alpha=0.05) -> tuple[float, float]`
  - `success_criterion(rs: list[float]) -> bool`  (95% CI low > 0 AND sum > 0)
  - `ruin_probability(rs, budget_r, horizon_trades, resamples=10_000, block=10, seed=7, demean=False, peak_relative=False) -> float`
  - `max_drawdown_path(rs: list[float]) -> float` and `cumulative_min(rs: list[float]) -> float`
  - `time_under_water_days(stream: list[tuple[int, float]]) -> float`
  - `trades_per_year(stream: list[tuple[int, float]]) -> float`
  - `required_n(mu: float, sigma: float, alpha=0.05, power=0.80) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fwd_analysis.py
import random
import unittest

from moonface.research import fwd_analysis as fa

_DAY_MS = 86_400_000


class BootstrapCITest(unittest.TestCase):
    def test_degenerate_inputs_collapse(self):
        self.assertEqual(fa.bootstrap_expectancy_ci([]), (0.0, 0.0))
        self.assertEqual(fa.bootstrap_expectancy_ci([1.5]), (1.5, 1.5))
        self.assertEqual(fa.bootstrap_expectancy_ci([2.0] * 50), (2.0, 2.0))

    def test_positive_edge_excludes_zero(self):
        rng = random.Random(1)
        rs = [(-2.0 if rng.random() < 0.3 else 4.0) for _ in range(300)]
        lo, hi = fa.bootstrap_expectancy_ci(rs, resamples=2000)
        self.assertGreater(lo, 0.0)
        self.assertLess(lo, hi)

    def test_deterministic(self):
        rs = [(-1.0) ** i * (1 + i % 3) for i in range(60)]
        self.assertEqual(fa.bootstrap_expectancy_ci(rs, resamples=500),
                         fa.bootstrap_expectancy_ci(rs, resamples=500))


class SuccessCriterionTest(unittest.TestCase):
    def test_flat_stream_fails(self):
        rng = random.Random(2)
        rs = [(-2.0 if rng.random() < 0.5 else 2.0) for _ in range(100)]
        self.assertFalse(fa.success_criterion(rs))

    def test_strong_stream_passes(self):
        rs = [4.0, 4.0, -2.0] * 40
        self.assertTrue(fa.success_criterion(rs))


class RuinTest(unittest.TestCase):
    def test_all_losing_hits_any_budget(self):
        p = fa.ruin_probability([-2.0] * 30, budget_r=-4.0,
                                horizon_trades=10, resamples=200)
        self.assertEqual(p, 1.0)

    def test_unreachable_budget(self):
        p = fa.ruin_probability([4.0] * 30, budget_r=-4.0,
                                horizon_trades=10, resamples=200)
        self.assertEqual(p, 0.0)

    def test_demean_raises_risk_for_positive_edge(self):
        rng = random.Random(3)
        rs = [(-2.0 if rng.random() < 0.25 else 4.0) for _ in range(200)]
        kw = dict(budget_r=-20.0, horizon_trades=100, resamples=500)
        self.assertGreaterEqual(fa.ruin_probability(rs, demean=True, **kw),
                                fa.ruin_probability(rs, demean=False, **kw))

    def test_peak_relative_at_least_cumulative(self):
        rng = random.Random(4)
        rs = [(-2.0 if rng.random() < 0.3 else 4.0) for _ in range(200)]
        kw = dict(budget_r=-12.0, horizon_trades=60, resamples=500)
        self.assertGreaterEqual(
            fa.ruin_probability(rs, peak_relative=True, **kw),
            fa.ruin_probability(rs, peak_relative=False, **kw))


class PathStatsTest(unittest.TestCase):
    def test_max_drawdown_and_cumulative_min(self):
        rs = [2.0, -3.0, -1.0, 5.0]
        self.assertEqual(fa.max_drawdown_path(rs), -4.0)
        self.assertEqual(fa.cumulative_min(rs), -2.0)

    def test_time_under_water(self):
        t0 = 1_600_000_000_000
        stream = [(t0, 1.0), (t0 + 1 * _DAY_MS, -2.0),
                  (t0 + 3 * _DAY_MS, 0.5), (t0 + 5 * _DAY_MS, 2.0)]
        # peak after trade 1 at t0; recovered at t0+5d -> 5 days under water
        self.assertEqual(fa.time_under_water_days(stream), 5.0)

    def test_trades_per_year(self):
        t0 = 1_600_000_000_000
        stream = [(t0 + i * _DAY_MS, 0.1) for i in range(366)]
        self.assertAlmostEqual(fa.trades_per_year(stream), 366.0, delta=2.0)


class RequiredNTest(unittest.TestCase):
    def test_point_estimate_power(self):
        # power=0.5 collapses to N = ceil((z_{.975} * sigma / mu)^2)
        self.assertEqual(fa.required_n(0.25, 1.4, power=0.5), 121)

    def test_monotonic_in_power(self):
        self.assertGreater(fa.required_n(0.25, 1.4, power=0.8),
                           fa.required_n(0.25, 1.4, power=0.5))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fwd_analysis.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.research.fwd_analysis'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/research/fwd_analysis.py
"""Pre-cutoff trade-stream analysis for the funding_fade_fwd registration
draft: block-bootstrap CI, drawdown-budget bootstrap, time-under-water, and
the verdict-trigger power calculation. Stdlib only; deterministic via
random.Random(seed). All resampling is moving-block (block of completed
trades) to preserve short-range clustering; nothing is ever interpolated."""
from __future__ import annotations

import math
import random
from statistics import NormalDist, pstdev

_DAY_MS = 86_400_000


def moving_block_resample(rs: list[float], rng: random.Random,
                          block: int = 10) -> list[float]:
    n = len(rs)
    out: list[float] = []
    while len(out) < n:
        start = rng.randrange(0, max(1, n - block + 1))
        out.extend(rs[start:start + block])
    return out[:n]


def bootstrap_expectancy_ci(rs: list[float], resamples: int = 10_000,
                            block: int = 10, seed: int = 42,
                            alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI on mean R. Degenerate inputs (n<2 or zero variance)
    collapse to (mean, mean) so the caller sees the collapse instead of a
    fake interval (capitulation-lane lesson)."""
    if not rs:
        return (0.0, 0.0)
    if len(rs) < 2 or len(set(rs)) == 1:
        m = sum(rs) / len(rs)
        return (m, m)
    rng = random.Random(seed)
    means = sorted(
        sum(sample) / len(sample)
        for sample in (moving_block_resample(rs, rng, block)
                       for _ in range(resamples)))
    lo = means[int(alpha / 2 * resamples)]
    hi = means[min(resamples - 1, int((1 - alpha / 2) * resamples))]
    return (lo, hi)


def success_criterion(rs: list[float]) -> bool:
    """Pre-committed EDGE FOUND rule: 95% CI low > 0 AND cumulative R > 0."""
    lo, _ = bootstrap_expectancy_ci(rs)
    return lo > 0.0 and sum(rs) > 0.0


def max_drawdown_path(rs: list[float]) -> float:
    equity = peak = dd = 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
    return dd


def cumulative_min(rs: list[float]) -> float:
    equity, low = 0.0, 0.0
    for r in rs:
        equity += r
        low = min(low, equity)
    return low


def ruin_probability(rs: list[float], budget_r: float, horizon_trades: int,
                     resamples: int = 10_000, block: int = 10, seed: int = 7,
                     demean: bool = False,
                     peak_relative: bool = False) -> float:
    """P(path touches budget_r within horizon_trades) by moving-block
    resampling. Kill semantics default to the spec's cumulative-R rule;
    peak_relative=True reports the (stricter) peak-to-trough variant."""
    if not rs:
        return float("nan")
    base = rs
    if demean:
        mu = sum(rs) / len(rs)
        base = [r - mu for r in rs]
    rng = random.Random(seed)
    hits = 0
    for _ in range(resamples):
        path: list[float] = []
        while len(path) < horizon_trades:
            start = rng.randrange(0, max(1, len(base) - block + 1))
            path.extend(base[start:start + block])
        equity = peak = 0.0
        for r in path[:horizon_trades]:
            equity += r
            peak = max(peak, equity)
            ref = equity - peak if peak_relative else equity
            if ref <= budget_r:
                hits += 1
                break
    return hits / resamples


def time_under_water_days(stream: list[tuple[int, float]]) -> float:
    """Longest stretch (days) from an equity peak to its recovery trade; an
    open stretch at the end counts up to the last trade's timestamp."""
    if not stream:
        return 0.0
    equity = peak = 0.0
    peak_ts = stream[0][0]
    worst_ms = 0
    under = False
    for ts, r in stream:
        equity += r
        if equity >= peak:
            if under:  # the recovering trade closes the underwater stretch
                worst_ms = max(worst_ms, ts - peak_ts)
                under = False
            peak = equity
            peak_ts = ts
        else:
            under = True
            worst_ms = max(worst_ms, ts - peak_ts)
    return worst_ms / _DAY_MS


def trades_per_year(stream: list[tuple[int, float]]) -> float:
    if len(stream) < 2:
        return 0.0
    span_days = (stream[-1][0] - stream[0][0]) / _DAY_MS
    if span_days <= 0:
        return 0.0
    return len(stream) / span_days * 365.0


def required_n(mu: float, sigma: float, alpha: float = 0.05,
               power: float = 0.80) -> int:
    """Trades for a two-sided (1-alpha) CI to exclude 0 with `power` when the
    true edge is mu. power=0.5 collapses to N = ceil((z*sigma/mu)^2)."""
    nd = NormalDist()
    z_a = nd.inv_cdf(1 - alpha / 2)
    z_b = nd.inv_cdf(power)
    return math.ceil(((z_a + z_b) * sigma / mu) ** 2)


def stream_sigma(rs: list[float]) -> float:
    return pstdev(rs) if len(rs) > 1 else 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_fwd_analysis.py -v`
Expected: all PASS. (`test_point_estimate_power`: `NormalDist().inv_cdf(0.5)` is 0.0, so N = ceil((1.959964*1.4/0.25)^2) = ceil(120.47) = 121.)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/fwd_analysis.py tests/test_fwd_analysis.py
git diff --cached --stat
git commit -m "feat(funding_fade_fwd): stream analysis (bootstrap CI, ruin, TUW, power)"
```

---

### Task 3: Null generator — per-segment funding shuffle

**Files:**
- Create: `src/moonface/research/fwd_null.py`
- Test: `tests/test_fwd_null.py`

**Interfaces:**
- Consumes: nothing project-specific.
- Produces (used by Task 4): `shuffle_funding_segments(funding: list[float | None], seed: int) -> list[float | None]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fwd_null.py
import unittest

from moonface.research.fwd_null import shuffle_funding_segments


class NullShuffleTest(unittest.TestCase):
    SERIES = [None, 0.1, 0.2, 0.3, None, None, 0.4, 0.5, 0.6, 0.7, None]

    def test_gaps_preserved_exactly(self):
        out = shuffle_funding_segments(self.SERIES, seed=0)
        self.assertEqual([i for i, v in enumerate(out) if v is None],
                         [i for i, v in enumerate(self.SERIES) if v is None])

    def test_values_preserved_per_segment(self):
        out = shuffle_funding_segments(self.SERIES, seed=0)
        self.assertEqual(sorted(out[1:4]), [0.1, 0.2, 0.3])
        self.assertEqual(sorted(out[6:10]), [0.4, 0.5, 0.6, 0.7])

    def test_deterministic_per_seed(self):
        self.assertEqual(shuffle_funding_segments(self.SERIES, seed=5),
                         shuffle_funding_segments(self.SERIES, seed=5))

    def test_seeds_differ(self):
        series = [float(i) for i in range(200)]
        self.assertNotEqual(shuffle_funding_segments(series, seed=0),
                            shuffle_funding_segments(series, seed=1))

    def test_input_not_mutated(self):
        original = list(self.SERIES)
        shuffle_funding_segments(self.SERIES, seed=0)
        self.assertEqual(self.SERIES, original)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fwd_null.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.research.fwd_null'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/research/fwd_null.py
"""Per-segment funding-shuffle null for the calibration guard (the
vol_compression lesson: a valid gate must FAIL on null data). Shuffling
funding within contiguous non-None segments destroys the funding->price
alignment while preserving the marginal distribution and the gap structure;
missing periods stay missing — never interpolated or zero-filled."""
from __future__ import annotations

import random


def shuffle_funding_segments(funding: list[float | None],
                             seed: int) -> list[float | None]:
    rng = random.Random(seed)
    out = list(funding)
    i, n = 0, len(out)
    while i < n:
        if out[i] is None:
            i += 1
            continue
        j = i
        while j < n and out[j] is not None:
            j += 1
        seg = out[i:j]
        rng.shuffle(seg)
        out[i:j] = seg
        i = j
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_fwd_null.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/fwd_null.py tests/test_fwd_null.py
git diff --cached --stat
git commit -m "feat(funding_fade_fwd): per-segment funding-shuffle null generator"
```

---

### Task 4: CLI — dryrun / analyze / null-guard / identity subcommands

**Files:**
- Create: `tools/funding_fade_fwd.py`
- Test: `tests/test_funding_fade_fwd_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3 (exact names as listed there).
- Produces: CLI writing to `experiments/funding_fade_fwd/`: `dryrun_report.json`, `streams.json`, `analysis.json`, `analysis.md`, `null_guard.json`. Functions `cmd_dryrun(cache_dir, out_root) -> int`, `cmd_analyze(out_root, budgets, months) -> int`, `cmd_null_guard(cache_dir, out_root, runs) -> int`, `cmd_identity(dd_budget_r, n_trades, months) -> int` (all return process exit codes; testable with injected `out_root`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_funding_fade_fwd_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.research import funding_fade_fwd as fwd
from tools.funding_fade_fwd import cmd_analyze, cmd_dryrun, cmd_identity


def _fake_loader(n=1300, spikes=(200, 250)):
    # Helpers duplicated from tests/test_funding_fade_fwd.py on purpose —
    # the tests/ tree is not an importable package.
    from moonface.foundation.models import Candle
    start_ms = fwd.CUTOFF_MS - (n + 1) * 14_400_000
    candles = []
    for i in range(n):
        close = 100.0 + 0.1 * i
        candles.append(Candle(timestamp_ms=start_ms + i * 14_400_000,
                              open=close - 0.05, high=close + 0.5,
                              low=close - 0.5, close=close, volume=1.0))
    funding = [1e-4 if i % 2 == 0 else -1e-4 for i in range(n)]
    for i in spikes:
        funding[i] = 1e-2
    return candles, funding


class DryrunCliTest(unittest.TestCase):
    def test_mismatch_returns_1_and_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            code = cmd_dryrun(cache_dir="unused", out_root=out,
                              loader=lambda _: _fake_loader())
            self.assertEqual(code, 1)  # synthetic data cannot match ARCHIVED
            report = json.loads((out / "dryrun_report.json").read_text())
            self.assertFalse(report["reproduced"])
            self.assertEqual(report["archived"], fwd.ARCHIVED)
            streams = json.loads((out / "streams.json").read_text())
            self.assertEqual(len(streams["research"]), 1)
            self.assertEqual(len(streams["tail"]), 1)


class AnalyzeCliTest(unittest.TestCase):
    def test_analyze_writes_tables_from_streams(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            day = 86_400_000
            research = [[1_600_000_000_000 + i * day,
                         (-2.0 if i % 4 == 0 else 1.0)] for i in range(120)]
            tail = [[1_700_000_000_000 + i * day, 1.0] for i in range(40)]
            (out / "streams.json").write_text(
                json.dumps({"research": research, "tail": tail}))
            code = cmd_analyze(out_root=out, budgets=[-40.0, -50.0, -64.0],
                               months=12, resamples=200)
            self.assertEqual(code, 0)
            analysis = json.loads((out / "analysis.json").read_text())
            self.assertEqual([b["budget_r"] for b in analysis["budgets"]],
                             [-40.0, -50.0, -64.0])
            for b in analysis["budgets"]:
                for key in ("p_ruin_measured", "p_ruin_zero_edge",
                            "p_ruin_measured_peak_relative",
                            "capital_at_risk_pct"):
                    self.assertIn(key, b)
            self.assertIn("required_n_power50", analysis["trigger"])
            self.assertIn("required_n_power80", analysis["trigger"])
            self.assertTrue((out / "analysis.md").exists())


class IdentityCliTest(unittest.TestCase):
    def test_identity_prints_hash(self):
        self.assertEqual(cmd_identity(-50.0, 123, 12), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_funding_fade_fwd_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.funding_fade_fwd'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python
# tools/funding_fade_fwd.py
"""funding_fade_fwd draft-preparation CLI. Subcommands:

  dryrun      reproduce the archived positioning_exits row on pre-cutoff data
  analyze     DD-budget candidates + verdict-trigger power calc from streams
  null-guard  100-seed funding-shuffle guard (must FAIL >= 95 of 100)
  identity    print the identity_hash for a (budget, N, months) choice

No subcommand can observe post-cutoff data: every load path goes through
funding_fade_fwd.load_pre_cutoff, which hard-clamps at CUTOFF_MS.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research import funding_fade_fwd as fwd
from moonface.research.fwd_analysis import (bootstrap_expectancy_ci,
                                            cumulative_min, max_drawdown_path,
                                            required_n, ruin_probability,
                                            stream_sigma, success_criterion,
                                            time_under_water_days,
                                            trades_per_year)
from moonface.research.fwd_null import shuffle_funding_segments

DEFAULT_OUT = Path("experiments/funding_fade_fwd")
DEFAULT_BUDGETS = [-40.0, -50.0, -64.0]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_dryrun(cache_dir: str, out_root: Path, loader=None) -> int:
    load = loader or fwd.load_pre_cutoff
    perp, funding = load(cache_dir)
    streams = fwd.regenerate(perp, funding)
    ok, got = fwd.reproduction_report(streams)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "streams.json").write_text(json.dumps(
        {"research": [[ts, r] for ts, r in streams.research],
         "tail": [[ts, r] for ts, r in streams.tail]}), encoding="utf-8")
    (out_root / "dryrun_report.json").write_text(json.dumps(
        {"generated": _now(), "archived": fwd.ARCHIVED, "regenerated": got,
         "reproduced": ok}, indent=2, sort_keys=True), encoding="utf-8")
    if ok:
        print("DRY-RUN REPRODUCED: all archived figures match exactly.")
        return 0
    print("DRY-RUN MISMATCH — STOP AND ASK (spec 5.2). No silent patching.")
    for k, v in fwd.ARCHIVED.items():
        if got[k] != v:
            print(f"  {k}: archived={v} regenerated={got[k]}")
    return 1


def _load_streams(out_root: Path) -> tuple[list, list]:
    data = json.loads((out_root / "streams.json").read_text(encoding="utf-8"))
    research = [(int(ts), float(r)) for ts, r in data["research"]]
    tail = [(int(ts), float(r)) for ts, r in data["tail"]]
    return research, tail


def cmd_analyze(out_root: Path, budgets: list[float], months: int,
                resamples: int = 10_000) -> int:
    research, tail = _load_streams(out_root)
    full = research + tail
    rs_full = [r for _, r in full]
    rs_research = [r for _, r in research]
    rs_tail = [r for _, r in tail]
    rate = trades_per_year(full)
    horizon = max(1, round(rate * months / 12.0))
    mu = sum(rs_research) / len(rs_research)
    sigma = stream_sigma(rs_research)
    rows = []
    for budget in budgets:
        rows.append({
            "budget_r": budget,
            "capital_at_risk_pct": round(abs(budget) * fwd.FRACTION * 100, 2),
            "p_ruin_measured": ruin_probability(rs_full, budget, horizon,
                                                resamples=resamples),
            "p_ruin_zero_edge": ruin_probability(rs_full, budget, horizon,
                                                 resamples=resamples,
                                                 demean=True),
            "p_ruin_measured_peak_relative": ruin_probability(
                rs_full, budget, horizon, resamples=resamples,
                peak_relative=True),
        })
    analysis = {
        "generated": _now(),
        "inputs": {"research_n": len(rs_research), "tail_n": len(rs_tail),
                   "research_mu": round(mu, 4), "research_sigma":
                   round(sigma, 4), "trades_per_year": round(rate, 2),
                   "horizon_trades": horizon, "months": months},
        "history": {
            "full_cumulative_min_r": round(cumulative_min(rs_full), 4),
            "full_max_dd_r": round(max_drawdown_path(rs_full), 4),
            "research_max_dd_r": round(max_drawdown_path(rs_research), 4),
            "time_under_water_days": round(time_under_water_days(full), 1),
        },
        "expectancy_ci": {
            "research_95": bootstrap_expectancy_ci(rs_research,
                                                   resamples=resamples),
            "tail_95": bootstrap_expectancy_ci(rs_tail, resamples=resamples),
        },
        "budgets": rows,
        "trigger": {
            "required_n_power50": required_n(mu, sigma, power=0.5),
            "required_n_power80": required_n(mu, sigma, power=0.8),
            "calendar_months": months,
        },
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    (out_root / "analysis.md").write_text(_render_analysis(analysis),
                                          encoding="utf-8")
    print(f"analysis written to {out_root}/analysis.{{json,md}}")
    return 0


def _render_analysis(a: dict) -> str:
    i, h, t = a["inputs"], a["history"], a["trigger"]
    lines = [
        "# funding_fade_fwd — pre-cutoff analysis (drafting input)", "",
        f"- generated: {a['generated']}",
        f"- research n={i['research_n']} mu={i['research_mu']}R "
        f"sigma={i['research_sigma']}R; tail n={i['tail_n']}",
        f"- trades/year {i['trades_per_year']}; "
        f"{i['months']}-month horizon = {i['horizon_trades']} trades",
        f"- history: cum-min {h['full_cumulative_min_r']}R, "
        f"max peak-DD {h['full_max_dd_r']}R "
        f"(research-only {h['research_max_dd_r']}R), "
        f"longest TUW {h['time_under_water_days']}d",
        f"- expectancy 95% CI: research {a['expectancy_ci']['research_95']}, "
        f"tail {a['expectancy_ci']['tail_95']}", "",
        "| budget R | capital at risk (f=0.01) | P(ruin, measured) | "
        "P(ruin, zero-edge) | P(ruin, peak-rel) |",
        "|---|---|---|---|---|",
    ]
    for b in a["budgets"]:
        lines.append(
            f"| {b['budget_r']} | {b['capital_at_risk_pct']}% | "
            f"{b['p_ruin_measured']:.4f} | {b['p_ruin_zero_edge']:.4f} | "
            f"{b['p_ruin_measured_peak_relative']:.4f} |")
    lines += [
        "",
        f"Verdict-trigger N (95% CI excludes 0): power 0.5 -> "
        f"{t['required_n_power50']} trades; power 0.8 -> "
        f"{t['required_n_power80']} trades; calendar floor "
        f"{t['calendar_months']} months. Later-of semantics; the human "
        "chooses the power level and budget at sign-off.",
    ]
    return "\n".join(lines) + "\n"


def cmd_null_guard(cache_dir: str, out_root: Path, runs: int = 100,
                   loader=None) -> int:
    load = loader or fwd.load_pre_cutoff
    perp, funding = load(cache_dir)
    passes = []
    for seed in range(runs):
        null_funding = shuffle_funding_segments(funding, seed)
        streams = fwd.regenerate(perp, null_funding)
        passes.append(success_criterion([r for _, r in streams.tail]))
    n_pass = sum(passes)
    guard_ok = (runs - n_pass) / runs >= 0.95
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "null_guard.json").write_text(json.dumps(
        {"generated": _now(), "runs": runs, "null_passes": n_pass,
         "fail_fraction": (runs - n_pass) / runs, "guard_ok": guard_ok,
         "criterion": "success_criterion on OOS-tail stream",
         "seeds": f"0..{runs - 1}"}, indent=2, sort_keys=True),
        encoding="utf-8")
    print(f"null guard: {runs - n_pass}/{runs} nulls FAIL the success "
          f"criterion -> guard_ok={guard_ok}")
    return 0 if guard_ok else 1


def cmd_identity(dd_budget_r: float, n_trades: int, months: int) -> int:
    print(fwd.identity_hash(dd_budget_r, n_trades, months))
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="funding_fade_fwd draft prep")
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-root", default=str(DEFAULT_OUT))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dryrun")
    a = sub.add_parser("analyze")
    a.add_argument("--budgets", type=float, nargs="+", default=DEFAULT_BUDGETS)
    a.add_argument("--months", type=int, default=12)
    a.add_argument("--resamples", type=int, default=10_000)
    g = sub.add_parser("null-guard")
    g.add_argument("--runs", type=int, default=100)
    ident = sub.add_parser("identity")
    ident.add_argument("--dd-budget-r", type=float, required=True)
    ident.add_argument("--n-trades", type=int, required=True)
    ident.add_argument("--months", type=int, default=12)
    args = p.parse_args()
    out_root = Path(args.out_root)
    if args.cmd == "dryrun":
        sys.exit(cmd_dryrun(args.cache_dir, out_root))
    if args.cmd == "analyze":
        sys.exit(cmd_analyze(out_root, args.budgets, args.months,
                             args.resamples))
    if args.cmd == "null-guard":
        sys.exit(cmd_null_guard(args.cache_dir, out_root, args.runs))
    if args.cmd == "identity":
        sys.exit(cmd_identity(args.dd_budget_r, args.n_trades, args.months))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_funding_fade_fwd_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full new-test suite together**

Run: `.venv/bin/python -m pytest tests/test_funding_fade_fwd.py tests/test_fwd_analysis.py tests/test_fwd_null.py tests/test_funding_fade_fwd_cli.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add tools/funding_fade_fwd.py tests/test_funding_fade_fwd_cli.py
git diff --cached --stat
git commit -m "feat(funding_fade_fwd): draft-prep CLI (dryrun/analyze/null-guard/identity)"
```

---

### Task 5: Execute the dry-run reproduction (pre-cutoff data only)

**Files:**
- Create (by the run): `experiments/funding_fade_fwd/dryrun_report.json`, `experiments/funding_fade_fwd/streams.json`

**Interfaces:**
- Consumes: Task 4 CLI. Network access to Binance is allowed ONLY for pre-cutoff backfill (the explicit `end_ms=CUTOFF_MS` makes over-fetch impossible; the clamp double-checks).

- [ ] **Step 1: Run the dry-run**

Run: `.venv/bin/python tools/funding_fade_fwd.py dryrun`
Expected: `DRY-RUN REPRODUCED: all archived figures match exactly.` and exit code 0.

- [ ] **Step 2: If (and only if) it reports MISMATCH — STOP**

This is spec §5.2. Do NOT touch the pipeline, the constants, or the tolerance. Write the mismatch table into `experiments/funding_fade_fwd/STATUS.md` under a heading `## ESCALATION — dry-run reproduction failure`, commit that file alone, and end the session by reporting to the human. Every subsequent task is blocked.

- [ ] **Step 3: Sanity-check the report (on success)**

Run: `cat experiments/funding_fade_fwd/dryrun_report.json`
Expected: `"reproduced": true`, regenerated values byte-identical to the ARCHIVED block.

- [ ] **Step 4: Commit the run artifacts**

```bash
git add experiments/funding_fade_fwd/dryrun_report.json experiments/funding_fade_fwd/streams.json
git diff --cached --stat
git commit -m "chore(funding_fade_fwd): dry-run reproduces archived row exactly"
```

---

### Task 6: Execute analysis + null guard (pre-cutoff data only)

**Files:**
- Create (by the runs): `experiments/funding_fade_fwd/analysis.json`, `analysis.md`, `null_guard.json`

**Interfaces:**
- Consumes: Task 4 CLI and Task 5's `streams.json`.

- [ ] **Step 1: Run the analysis**

Run: `.venv/bin/python tools/funding_fade_fwd.py analyze`
Expected: exit 0; `analysis.md` shows the three-budget table, history stats (expect research max peak-DD −32.0R), CIs, and both N values.

- [ ] **Step 2: Run the null guard**

Run: `.venv/bin/python tools/funding_fade_fwd.py null-guard`
Expected: `null guard: K/100 nulls FAIL the success criterion -> guard_ok=True` with K ≥ 95. If `guard_ok=False`, that is the vol_compression failure mode — the success criterion passes on shuffled data. STOP: record the result in STATUS.md under `## ESCALATION — null guard failure`, commit, report to the human. Tasks 7–8 are blocked on the guard.

- [ ] **Step 3: Commit the artifacts**

```bash
git add experiments/funding_fade_fwd/analysis.json experiments/funding_fade_fwd/analysis.md experiments/funding_fade_fwd/null_guard.json
git diff --cached --stat
git commit -m "chore(funding_fade_fwd): pre-cutoff analysis + null-guard artifacts"
```

---

### Task 7: Draft D1 (REGISTRATION_DRAFT.md) and D2 (PIPELINE_FREEZE_PLAN.md)

**Files:**
- Create: `experiments/funding_fade_fwd/REGISTRATION_DRAFT.md`
- Create: `experiments/funding_fade_fwd/PIPELINE_FREEZE_PLAN.md`

**Interfaces:**
- Consumes: `analysis.json` / `analysis.md` values (marked `«analysis: key»` below — substitute the real numbers, never leave a marker in the committed file), `null_guard.json`, and the frozen constants from Task 1.

- [ ] **Step 1: Write REGISTRATION_DRAFT.md**

Use exactly this skeleton; replace every `«analysis: …»` marker with the number from `analysis.json` and every `«guard: …»` from `null_guard.json`:

```markdown
# funding_fade_fwd — Pre-Registration DRAFT (awaiting human sign-off)

**Status:** DRAFT. Nothing here is frozen until human sign-off (D-gate).
No market data after 2026-06-10T06:51:46Z has been observed in preparing
this draft (clamp-enforced; see PIPELINE_FREEZE_PLAN.md).

## 1. Strategy identity (frozen, copied verbatim from the original row)

- Source: `experiments/positioning_exits/20260610T065146Z/`, row 2.
- Entry: `funding_fade {"window": 60, "z_thr": 1.5}` — rolling z-score of the
  8h funding rate over 60 aligned 4h bars; z >= +1.5 -> SHORT, z <= -1.5 ->
  LONG, edge-triggered (implementation:
  `src/moonface/research/edge/funding_signals.py::make_funding_fade`).
- Exit: `fixed_bracket {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}` —
  static stop 2xATR(14) and TP 4xATR(14) from entry close, 48-bar cap
  (implementation: `src/moonface/foundation/exits.py::fixed_bracket`).
- R definition: 1R = 1 ATR(14) at entry. A stop hit = −2.0R; a TP hit =
  +4.0R; a cap expiry = mark-to-close in ATR units.
- Original archived result: research 254 trades, +64.7507R, +0.2549R/trade,
  max peak-DD −32.0R; OOS 68 trades, +76.7285R, +1.1284R/trade.
- Original rejection reasons (both, stated honestly): (1) the row-level
  −15R research-drawdown cap — the sole failing condition in
  `exit_score.py::exit_gate`; (2) the program-level single-entry robustness
  rule (fixed_bracket passed on only 1 of 3 entries). This forward program
  tests the single frozen cell on unseen forward data; it claims no
  cross-entry robustness.
- Program identity_hash (frozen at sign-off, over rules + every parameter
  in this document): computed by
  `.venv/bin/python tools/funding_fade_fwd.py identity --dd-budget-r <B>
  --n-trades <N> --months 12` once the human picks B and N.

## 2. Instrument & feed

- BTC USDS-M perpetual: binance `BTC/USDT:USDT`, 4h OHLCV via ccxt
  `fetch_ohlcv`; funding via ccxt `fetchFundingRateHistory` (8h cadence),
  as-of joined to bar opens (`align_funding`, no lookahead). Identical
  exchange, symbols, timeframe, and join as the original research. No known
  feed differences; any discovered difference triggers spec §5.4.

## 3. Drawdown budget (candidates — THE HUMAN CHOOSES; not pre-selected)

Derived only from pre-cutoff data (research + burned OOS, n=322 trades;
streams regenerated by the frozen pipeline, dry-run verified). Kill
semantics: cumulative forward R <= budget at any point -> KILL (the
peak-relative variant is reported for reference; it is stricter and is NOT
the kill rule). At f = 0.01 per R, a budget of −B R is −B% of initial
equity; a single stop costs 2R x 0.01 = 2%.

| budget R | capital at risk | P(hit, measured edge) | P(hit, zero edge) | P(hit, peak-rel) |
|---|---|---|---|---|
| −40 | 40% | «analysis: budgets[0].p_ruin_measured» | «analysis: budgets[0].p_ruin_zero_edge» | «analysis: budgets[0].p_ruin_measured_peak_relative» |
| −50 | 50% | «analysis: budgets[1].p_ruin_measured» | «analysis: budgets[1].p_ruin_zero_edge» | «analysis: budgets[1].p_ruin_measured_peak_relative» |
| −64 | 64% | «analysis: budgets[2].p_ruin_measured» | «analysis: budgets[2].p_ruin_zero_edge» | «analysis: budgets[2].p_ruin_measured_peak_relative» |

Anchors: research-period peak-DD was −32.0R; pre-cutoff cumulative minimum
was «analysis: history.full_cumulative_min_r»R; longest time-under-water
«analysis: history.time_under_water_days» days. A budget that would have
killed the known path is incoherent with the premise; −40R carries the
thinnest safety margin over the known −32R.

## 4. Sizing

Fixed fractional f = 0.01 of initial equity per R. No compounding, no
equity scaling, no vol targeting (the vol-targeting lever is closed:
funding_fade_voltarget, 2026-07-01).

## 5. Verdict trigger (pre-committed, later-of)

- N completed forward trades: N = «human choice, from analysis.md: 
  power 0.5 -> «analysis: trigger.required_n_power50» trades, power 0.8 ->
  «analysis: trigger.required_n_power80» trades» (pre-cutoff trade rate
  «analysis: inputs.trades_per_year»/yr => a 12-month window yields ~
  «analysis: inputs.horizon_trades» trades), AND
- 12 calendar months from sign-off.
One verdict, written once. No interim aggregate-P&L observation. Trade
counting for the trigger is mechanical (completed exits), not performance
peeking.

## 6. Kill / VOID rules (terminal, any one suffices)

1. KILL — cumulative forward R <= the pre-committed budget at any point.
2. VOID — > 5% of the forward window unreconstructible from feed + Binance
   Vision archive (distinct from KILL; a VOID writes no edge verdict).
3. VOID — BTC USDS-M delisting or structural funding-mechanism change
   (interval or formula), with a dated note describing the change.

## 7. Success criterion (pre-committed)

EDGE FOUND iff, on the forward trade stream at verdict time: the 95%
moving-block-bootstrap CI (block 10, 10,000 resamples, seed 42) on per-trade
expectancy excludes 0 from above AND cumulative R > 0. Anything else on a
completed window is EDGE NOT CONFIRMED (terminal negative).

## 8. Null-calibration guard

Guard run (pre-cutoff, completed before this draft): 100 per-segment
funding-shuffles (seeds 0–99, gap structure preserved, missing periods
dropped never filled) through the identical frozen pipeline; the success
criterion must FAIL on >= 95/100. Result: «guard: null_passes» /100 nulls
passed -> fail fraction «guard: fail_fraction», guard_ok = «guard:
guard_ok». The same guard re-runs, same seeds, on the frozen commit before
the forward evaluation is trusted.

## 9. Ambiguity protocol

Any verdict-affecting ambiguity discovered after forward data is observed
VOIDS the cycle. Non-gating ambiguities get dated clarification notes
appended to STATUS.md. Arbitrary verdict-affecting conventions resolve
toward KILL (stricter counting, higher thresholds).

## 10. Citations & closed-door statement

- Original verdict: `experiments/positioning_exits/20260610T065146Z/` and
  the core program's NEGATIVE conclusion
  (`docs/findings/PROGRAM_CONCLUSION.md`, "The one lever deliberately not
  pulled" — this lane is its recorded sole data-motivated successor).
- `funding_fade_voltarget` (closed negative 2026-07-01) kill rule reads "no
  v2, no fraction grid, no budget relaxation." Human ruling 2026-07-13
  (recorded in the design doc): that rule bound its own lane — the
  vol/risk-targeting lever on ETH/SOL historical OOS. This program changes
  exactly one variable vs the original registration (the DD budget), on
  forward-only data, with the formula frozen; it is not a formula re-sweep
  and reopens no closed family.
```

- [ ] **Step 2: Verify no markers remain**

Run: `grep -n "«" experiments/funding_fade_fwd/REGISTRATION_DRAFT.md; echo "exit=$?"`
Expected: no output lines; `exit=1` (all markers substituted).

- [ ] **Step 3: Write PIPELINE_FREEZE_PLAN.md**

```markdown
# funding_fade_fwd — Pipeline Freeze Plan

## Code paths the forward evaluation uses (exhaustive)

| Stage | Path |
|---|---|
| OHLCV ingestion | `src/moonface/foundation/data.py::fetch_history` + `OhlcvCache` |
| Funding ingestion | `src/moonface/foundation/series.py::fetch_funding_history` + `FundingCache` |
| Funding alignment | `src/moonface/foundation/series.py::align_funding` |
| Entry signal | `src/moonface/research/edge/funding_signals.py::make_funding_fade` |
| Exit simulation | `src/moonface/foundation/exits.py::fixed_bracket` (via `EXIT_REGISTRY`) |
| R streams / split | `src/moonface/research/edge/exit_score.py::exit_r_streams`, `src/moonface/research/sizing.py::split_research_tail` |
| Summaries | `src/moonface/foundation/metrics.py::summarize_r` |
| Orchestration/clamp | `src/moonface/research/funding_fade_fwd.py` |
| CI / ruin / power | `src/moonface/research/fwd_analysis.py` |
| Null generator | `src/moonface/research/fwd_null.py` |
| CLI / reports | `tools/funding_fade_fwd.py` |

## Freeze mechanics

- At human sign-off, record in STATUS.md: the git commit hash containing all
  paths above, the identity_hash, the chosen DD budget, and the chosen N.
- The forward evaluation is a SINGLE run of a forward-mode entry point added
  only after sign-off, executed from the pinned commit (e.g. a detached
  worktree at that hash). One spend; the run writes the verdict file
  directly. Re-runs require a written VOID/amendment note — there is no
  silent second spend.
- Between sign-off and verdict: no code changes to any listed path. If an
  unrelated repo change forces one (e.g. dependency breakage), that is a
  spec §5 escalation with a dated note, decided by the human.

## Dry-run record

- `dryrun_report.json` reproduced the archived row EXACTLY (tolerance:
  archived reported precision). Window: 3y ending 2026-06-10T06:51:46Z;
  `oos_tail_bars=1095`, `warmup=60`, `future_bars=48`.
- Reproduction failure policy: STOP and ask; never patch silently (spec §5.2).

## Forward-run data plan (Approach A, design §5)

- No collector, no daemon. At trigger time, one retroactive fetch:
  `start_ms = CUTOFF_MS` (minus the 60-bar funding warmup, which overlaps
  burned data only for indicator warmup and is discarded for trade
  counting: entries before CUTOFF_MS are excluded), `end_ms = trigger date`.
- Reconstructibility check against kill rule 2 runs BEFORE any performance
  aggregation: bar-count and funding-cadence audit vs expected calendar.
```

- [ ] **Step 4: Commit**

```bash
git add experiments/funding_fade_fwd/REGISTRATION_DRAFT.md experiments/funding_fade_fwd/PIPELINE_FREEZE_PLAN.md
git diff --cached --stat
git commit -m "docs(funding_fade_fwd): D1 registration draft + D2 pipeline freeze plan"
```

---

### Task 8: D3 STATUS.md + final verification + hand to human (HARD STOP)

**Files:**
- Create: `experiments/funding_fade_fwd/STATUS.md`

- [ ] **Step 1: Write STATUS.md**

```markdown
# funding_fade_fwd — STATUS

- **Phase:** DRAFT COMPLETE — awaiting human sign-off (D-gate, hard stop).
- **Today:** (substitute the actual run date, ISO format)
- **Frozen already:** strategy formula (verbatim from the original row);
  pipeline code paths (see PIPELINE_FREEZE_PLAN.md); dry-run reproduced the
  archived row exactly; null guard result recorded in REGISTRATION_DRAFT §8.
- **Pending human choices at sign-off:** DD budget (−40 / −50 / −64 R),
  verdict-trigger N (power 0.5 vs 0.8), then: identity_hash computation,
  pipeline commit pin.
- **Forward window:** accruing unseen since 2026-06-10T06:51:46Z. Not
  observed by this drafting phase (clamp-enforced).
- **Amendment window:** OPEN until sign-off; closes permanently at sign-off.
- **Data hygiene incidents:** none. (Any incident would appear here with a
  dated ESCALATION heading and would have halted work.)
```

- [ ] **Step 2: Full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: everything passes (no regressions in the pre-existing suite).

- [ ] **Step 3: Verify no post-cutoff observation happened**

Run:
```bash
grep -n "reproduced" experiments/funding_fade_fwd/dryrun_report.json
.venv/bin/python -c "
import json, sys
sys.path.insert(0, 'src')
from moonface.research.funding_fade_fwd import CUTOFF_MS
d = json.load(open('experiments/funding_fade_fwd/streams.json'))
print(max(ts for ts, _ in d['research'] + d['tail']) < CUTOFF_MS)
"
```
Expected: `"reproduced": true` and `True` (no trade timestamp at/after the cutoff).

- [ ] **Step 4: Commit**

```bash
git add experiments/funding_fade_fwd/STATUS.md
git diff --cached --stat
git commit -m "docs(funding_fade_fwd): D3 status — draft complete, awaiting sign-off"
```

- [ ] **Step 5: STOP**

Present to the human: the three documents, the analysis table, the null-guard result, and the two N options. Do NOT compute a final identity_hash, do NOT pin a commit, do NOT touch forward data. The next action in this program is the human's.
