# Multi-family exit-free drift screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the price-only drift screen to the funding, OI/positioning, and orderbook-imbalance feature families, scoring directional drift exit-free across the 16-asset 4h pool with per-family frozen primary horizons.

**Architecture:** Reuse the existing path-aware statistics primitives in `src/moonface/research/drift_screen.py` (event outcome in R, MAE, sign test, Stouffer Z, tripartite verdict). Add MFE and per-event sign rate to those shared primitives. Add a new bundle-aware screening path (`screen_family`) that resolves events through `entries.generate_entries(family, params, DataBundle)`, leaving the existing candles-only `screen_signal` (price path) untouched. Add one new orderbook-imbalance generator using the existing `bookdepth_data` loader. A new CLI freezes per-family primary horizons and per-horizon recalibrated floors in a pre-registration document, then screens and writes a leaderboard.

**Tech Stack:** Python 3.12, stdlib `statistics`/`math`, `unittest`/`pytest`, existing `moonface.research` + `moonface.backtest.edge` packages. No new dependencies.

**Spec:** `docs/research-log/specs/2026-06-16-multi-family-drift-screen-design.md`

---

## File Structure

**Create:**
- `src/moonface/backtest/edge/ob_imbalance_signals.py` — per-bar imbalance aggregation + the `ob_imbalance_follow` generator factory.
- `src/moonface/research/multifamily_loader.py` — per-asset `DataBundle` loader for the 16-asset pool (candles + funding + metrics field + bookdepth imbalance), with coverage gating.
- `tools/drift_screen_multifamily.py` — `phase-a` / `register` / `run` CLI for the multi-family screen.
- `experiments/drift_screen_multifamily/PREREGISTRATION.md` — frozen design + recalibrated per-horizon floors (written during execution, Task 9).
- `tests/test_ob_imbalance_signals.py`
- `tests/test_multifamily_loader.py`
- `tests/test_multifamily_screen.py`
- `tests/test_drift_screen_multifamily_cli.py`

**Modify:**
- `src/moonface/research/drift_screen.py` — `event_outcome` returns `(ret_r, mae_r, mfe_r)`; `asset_path_stats` adds `mean_mfe_r` + `sign_rate`; add `score_family_on_asset`, `screen_family`, `horizon_curve`.
- `src/moonface/research/bundle.py` — add `bookdepth` field to `DataBundle`.
- `src/moonface/research/entries.py` — register `ob_imbalance_follow`, route to `bundle.bookdepth`.
- `tests/test_drift_screen.py` — update existing 2-tuple outcome tests to the new 3-tuple shape.

---

## Task 1: Add MFE + per-event sign rate to the shared path primitives

**Files:**
- Modify: `src/moonface/research/drift_screen.py:22-57`
- Test: `tests/test_drift_screen.py`

`event_outcome` currently returns `(ret_r, mae_r)`. Add the maximum *favorable* excursion in R (mirror of MAE: `bar.high` for LONG, `bar.low` for SHORT, the best in-horizon move, `>= 0`). `asset_path_stats` gains `mean_mfe_r` and `sign_rate` (fraction of events with `ret_r > 0`). The price-path `screen_signal` inherits these automatically since it calls `asset_path_stats`.

- [ ] **Step 1: Update the existing outcome tests to the 3-tuple shape (write the failing tests)**

In `tests/test_drift_screen.py`, replace the body of `TestEventOutcome` assertions that unpack `out` and the `TestAssetPathStats` fixtures. Apply these edits:

In `test_long_drift_no_adverse_excursion`:
```python
        out = event_outcome(candles, i=2, side="LONG", h=3, atr_period=2)
        self.assertIsNotNone(out)
        ret_r, mae_r, mfe_r = out
        self.assertGreater(ret_r, 0.0)
        self.assertEqual(mae_r, 0.0)
        self.assertGreaterEqual(mfe_r, ret_r)  # favorable excursion >= endpoint
```

In `test_long_drift_with_midhorizon_dip`:
```python
        out = event_outcome(candles, i=2, side="LONG", h=2, atr_period=2)
        self.assertIsNotNone(out)
        ret_r, mae_r, mfe_r = out
        self.assertGreater(ret_r, 0.0)
        self.assertLess(mae_r, 0.0)
        self.assertGreaterEqual(mfe_r, 0.0)
        self.assertAlmostEqual(ret_r / -mae_r, 6.0 / 10.0, places=4)
```

In `test_short_uses_high_for_adverse`:
```python
        out = event_outcome(candles, i=2, side="SHORT", h=2, atr_period=2)
        ret_r, mae_r, mfe_r = out
        self.assertGreater(ret_r, 0.0)
        self.assertLess(mae_r, 0.0)
        self.assertGreaterEqual(mfe_r, 0.0)
```

Add a new MFE-specific test to `TestEventOutcome`:
```python
    def test_mfe_captures_best_favorable_for_long(self):
        # LONG entry close 100, spikes high 130 mid-horizon, closes 100 (flat)
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry i=2
            _candle(3, 100, 130, 100, 100),  # favorable high 130
            _candle(4, 100, 101, 99, 100),
        ]
        ret_r, mae_r, mfe_r = event_outcome(candles, i=2, side="SHORT", h=2,
                                            atr_period=2) or (0, 0, 0)
        # SHORT: favorable excursion uses bar.low; rerun as LONG below
        ret_r, mae_r, mfe_r = event_outcome(candles, i=2, side="LONG", h=2,
                                            atr_period=2)
        self.assertGreater(mfe_r, 0.0)          # saw +30 at the high
        self.assertAlmostEqual(ret_r, 0.0)      # closed flat
```

Replace `TestAssetPathStats` fixtures (3-tuples now) and add sign_rate/mfe assertions:
```python
class TestAssetPathStats(unittest.TestCase):
    def test_aggregates_ret_mae_mfe_and_sign(self):
        outcomes = [(2.0, -1.0, 3.0), (4.0, -3.0, 5.0), (-3.0, -2.0, 1.0)]
        s = asset_path_stats(outcomes)
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["mean_ret_r"], 1.0)
        self.assertAlmostEqual(s["mean_abs_mae_r"], 2.0)
        self.assertAlmostEqual(s["mean_mfe_r"], 3.0)
        self.assertAlmostEqual(s["sign_rate"], 2.0 / 3.0)
        self.assertNotEqual(s["t"], 0.0)

    def test_empty_is_zeroed(self):
        s = asset_path_stats([])
        self.assertEqual(s["n"], 0)
        self.assertEqual(s["mean_ret_r"], 0.0)
        self.assertEqual(s["mean_abs_mae_r"], 0.0)
        self.assertEqual(s["mean_mfe_r"], 0.0)
        self.assertEqual(s["sign_rate"], 0.0)
        self.assertEqual(s["t"], 0.0)

    def test_t_matches_oibuild_asset_stats(self):
        from moonface.research.oibuild_study import asset_stats
        outcomes = [(2.0, -1.0, 3.0), (4.0, -3.0, 5.0),
                    (3.0, -2.0, 4.0), (1.0, -0.5, 2.0)]
        rets = [r for r, _, _ in outcomes]
        self.assertAlmostEqual(asset_path_stats(outcomes)["t"],
                               asset_stats(rets)["t"], places=10)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_drift_screen.py -q`
Expected: FAIL — `event_outcome` returns a 2-tuple (ValueError unpacking 3), `asset_path_stats` has no `mean_mfe_r`/`sign_rate` keys.

- [ ] **Step 3: Implement MFE in `event_outcome` and the two new stats**

In `src/moonface/research/drift_screen.py`, replace `event_outcome` and `asset_path_stats`:
```python
def event_outcome(candles: list[Candle], i: int, side: str, h: int,
                  atr_period: int) -> tuple[float, float, float] | None:
    """Per-event (ret_r, mae_r, mfe_r) in R units over a fixed horizon h.

    ret_r = side * (close[i+h] - close[i]) / unit   (forward move in R)
    mae_r = worst intra-horizon excursion AGAINST the position, <= 0
            (bar.low for LONG, bar.high for SHORT).
    mfe_r = best intra-horizon excursion IN FAVOUR, >= 0
            (bar.high for LONG, bar.low for SHORT).
    Returns None when the entry is untradeable (unit None) or there are
    fewer than h future bars."""
    unit = _risk(candles, i, 1.0, atr_period)
    if unit is None or i + h >= len(candles):
        return None
    entry = candles[i].close
    sign = 1.0 if side == "LONG" else -1.0
    ret_r = sign * (candles[i + h].close - entry) / unit
    worst = 0.0
    best = 0.0
    for k in range(1, h + 1):
        bar = candles[i + k]
        adverse = (bar.low - entry) if side == "LONG" else (entry - bar.high)
        favorable = (bar.high - entry) if side == "LONG" else (entry - bar.low)
        worst = min(worst, adverse / unit)
        best = max(best, favorable / unit)
    return ret_r, worst, best


def asset_path_stats(outcomes: list[tuple[float, float, float]]) -> dict:
    """One asset's evidence: mean forward R, mean absolute adverse R, mean
    favorable R, the per-event positive sign rate, and the ret_r t-stat
    (reusing oibuild's asset_stats so the magnitude test is identical across
    studies)."""
    if not outcomes:
        return {"n": 0, "mean_ret_r": 0.0, "mean_abs_mae_r": 0.0,
                "mean_mfe_r": 0.0, "sign_rate": 0.0, "t": 0.0}
    rets = [r for r, _, _ in outcomes]
    maes = [abs(m) for _, m, _ in outcomes]
    mfes = [f for _, _, f in outcomes]
    base = asset_stats(rets)
    pos = sum(1 for r in rets if r > 0)
    return {"n": base["n"], "mean_ret_r": base["mean"],
            "mean_abs_mae_r": fmean(maes), "mean_mfe_r": fmean(mfes),
            "sign_rate": pos / len(rets), "t": base["t"]}
```

Update the `score_signal_on_asset` accumulator type hint (it appends `event_outcome` results into a list typed `list[tuple[float, float]]`): change to `list[tuple[float, float, float]]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_drift_screen.py -q`
Expected: PASS (all tests, including the existing `TestScoreSignalOnAsset`/`TestScreenSignal` price-path tests which still pass through the shared primitives).

- [ ] **Step 5: Run ruff and commit**

Run: `ruff check src/moonface/research/drift_screen.py tests/test_drift_screen.py`
Expected: no errors.
```bash
git add src/moonface/research/drift_screen.py tests/test_drift_screen.py
git commit -m "feat(drift-screen): add MFE + per-event sign rate to path stats"
```

---

## Task 2: Orderbook-imbalance bar aggregation + generator

**Files:**
- Create: `src/moonface/backtest/edge/ob_imbalance_signals.py`
- Test: `tests/test_ob_imbalance_signals.py`

The bookdepth loader produces `(ts_ms, imbalance)` snapshot points (`bookdepth_data.imbalance_points`). We need (a) a per-4h-bar **mean** imbalance series aligned to candles, and (b) a symmetric follow generator mirroring `positioning_signals._make_level_follow`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ob_imbalance_signals.py`:
```python
import unittest

from moonface.models import Candle
from moonface.backtest.edge.ob_imbalance_signals import (
    bar_mean_imbalance, make_ob_imbalance_follow)

H4 = 4 * 3_600_000


def _c(i, close=100.0):
    return Candle(i * H4, close, close + 1, close - 1, close, 1000.0)


class TestBarMeanImbalance(unittest.TestCase):
    def test_means_snapshots_inside_each_bar(self):
        candles = [_c(0), _c(1), _c(2)]
        # bar 0 = [0, H4): two snapshots 0.2 and 0.4 -> mean 0.3
        # bar 1 = [H4, 2H4): one snapshot -0.5
        # bar 2 = [2H4, 3H4): no snapshots -> None
        points = [(10, 0.2), (H4 - 5, 0.4), (H4 + 10, -0.5)]
        series = bar_mean_imbalance(candles, points)
        self.assertEqual(len(series), 3)
        self.assertAlmostEqual(series[0], 0.3)
        self.assertAlmostEqual(series[1], -0.5)
        self.assertIsNone(series[2])

    def test_empty_points_all_none(self):
        candles = [_c(0), _c(1)]
        self.assertEqual(bar_mean_imbalance(candles, []), [None, None])


class TestObImbalanceFollow(unittest.TestCase):
    def _ramp_candles(self, n):
        return [_c(i) for i in range(n)]

    def test_high_bid_imbalance_goes_long(self):
        n = 40
        candles = self._ramp_candles(n)
        # flat imbalance then a strong positive (bid-side) spike at i=30
        feature = [0.0] * n
        feature[30] = 5.0
        gen = make_ob_imbalance_follow(feature)
        out = gen(candles, {"window": 20, "z_thr": 1.5})
        self.assertIn((30, "LONG"), out)

    def test_strong_ask_imbalance_goes_short(self):
        n = 40
        candles = self._ramp_candles(n)
        feature = [0.0] * n
        feature[30] = -5.0
        gen = make_ob_imbalance_follow(feature)
        out = gen(candles, {"window": 20, "z_thr": 1.5})
        self.assertIn((30, "SHORT"), out)

    def test_symmetry_mirrored_feature_mirrors_sides(self):
        n = 40
        candles = self._ramp_candles(n)
        feature = [0.0] * n
        feature[30] = 4.0
        pos = make_ob_imbalance_follow(feature)(candles,
                                                {"window": 20, "z_thr": 1.5})
        neg_feat = [-v for v in feature]
        neg = make_ob_imbalance_follow(neg_feat)(candles,
                                                 {"window": 20, "z_thr": 1.5})
        flip = {(i, "SHORT" if s == "LONG" else "LONG") for i, s in pos}
        self.assertEqual(set(neg), flip)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_ob_imbalance_signals.py -q`
Expected: FAIL — module `ob_imbalance_signals` does not exist.

- [ ] **Step 3: Implement the module**

Create `src/moonface/backtest/edge/ob_imbalance_signals.py`:
```python
"""Order-book imbalance hypothesis family over the Binance Vision bookDepth
archive (±1% band bid/ask notional).

Pre-registered mechanism, one direction (follow): resting depth imbalance is
informed pressure, so strong bid-side imbalance predicts positive forward
drift and strong ask-side imbalance predicts negative forward drift. The
signal is symmetric by construction. No exits, stops, TPs, or grids are fit
here — this is a mechanism generator only.

The generator sees candles plus one aligned per-bar imbalance series (the mean
of the ~30s snapshots inside each bar). It reuses the positioning family's
rolling-window z-score follow shape so the magnitude test is identical across
studies."""
from __future__ import annotations

from statistics import fmean

from moonface.backtest.edge.positioning_signals import _make_level_follow
from moonface.models import Candle

Entry = tuple[int, str]


def bar_mean_imbalance(candles: list[Candle],
                       points: list[tuple[int, float]]) -> list[float | None]:
    """Per-bar mean imbalance aligned 1:1 with candles. Each bar spans
    [candle.timestamp_ms, next candle's timestamp_ms); the last bar uses the
    same width as the previous one. A bar with no snapshots is None.

    No lookahead: snapshot ts must fall within the bar's own half-open window,
    and the bar's forward return is only ever scored from its close onward."""
    if not candles:
        return []
    width = (candles[1].timestamp_ms - candles[0].timestamp_ms
             if len(candles) > 1 else 0)
    pts = sorted(points)
    series: list[float | None] = []
    j = 0
    for idx, c in enumerate(candles):
        start = c.timestamp_ms
        end = (candles[idx + 1].timestamp_ms if idx + 1 < len(candles)
               else start + width)
        while j < len(pts) and pts[j][0] < start:
            j += 1
        bucket = []
        k = j
        while k < len(pts) and pts[k][0] < end:
            bucket.append(pts[k][1])
            k += 1
        series.append(fmean(bucket) if bucket else None)
    return series


def make_ob_imbalance_follow(feature: list[float | None]):
    """Follow resting ±1% depth imbalance at rolling-window extremes:
    z >= z_thr -> LONG, z <= -z_thr -> SHORT (symmetric)."""
    return _make_level_follow(feature)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_ob_imbalance_signals.py -q`
Expected: PASS.

- [ ] **Step 5: Run ruff and commit**

Run: `ruff check src/moonface/backtest/edge/ob_imbalance_signals.py tests/test_ob_imbalance_signals.py`
Expected: no errors.
```bash
git add src/moonface/backtest/edge/ob_imbalance_signals.py tests/test_ob_imbalance_signals.py
git commit -m "feat(ob-imbalance): per-bar imbalance aggregation + follow generator"
```

---

## Task 3: Add `bookdepth` to DataBundle and register the family in entries

**Files:**
- Modify: `src/moonface/research/bundle.py:17-27`
- Modify: `src/moonface/research/entries.py`
- Test: `tests/test_multifamily_screen.py` (a focused entries test; the file is extended in Task 5)

- [ ] **Step 1: Write the failing test**

Create `tests/test_multifamily_screen.py`:
```python
import unittest

from moonface.models import Candle
from moonface.research.bundle import DataBundle
from moonface.research.entries import generate_entries, known_families

H4 = 4 * 3_600_000


def _c(i, close=100.0):
    return Candle(i * H4, close, close + 1, close - 1, close, 1000.0)


class TestEntriesObImbalance(unittest.TestCase):
    def test_ob_imbalance_follow_is_known(self):
        self.assertIn("ob_imbalance_follow", known_families())

    def test_routes_to_bundle_bookdepth(self):
        n = 40
        candles = [_c(i) for i in range(n)]
        bookdepth = [0.0] * n
        bookdepth[30] = 5.0
        bundle = DataBundle(candles=candles, bookdepth=bookdepth)
        out = generate_entries("ob_imbalance_follow",
                               {"window": 20, "z_thr": 1.5}, bundle)
        self.assertIn((30, "LONG"), out)

    def test_missing_bookdepth_raises(self):
        bundle = DataBundle(candles=[_c(i) for i in range(5)])
        with self.assertRaises(ValueError):
            generate_entries("ob_imbalance_follow",
                             {"window": 2, "z_thr": 1.5}, bundle)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_multifamily_screen.py -q`
Expected: FAIL — `DataBundle` has no `bookdepth` field / `ob_imbalance_follow` unknown.

- [ ] **Step 3: Add the `bookdepth` field to DataBundle**

In `src/moonface/research/bundle.py`, edit the dataclass:
```python
@dataclass(frozen=True)
class DataBundle:
    """Everything a hypothesis can see for one asset. funding/basis/feature/
    bookdepth are aligned 1:1 with candles (as-of joins, no lookahead) or None
    when not loaded. `feature` is a cross-asset close series (e.g. ETH for
    lead-lag) or a metrics series; `bookdepth` is the per-bar mean ±1% depth
    imbalance."""

    candles: list[Candle]
    funding: list[float | None] | None = None
    basis: list[float | None] | None = None
    feature: list[float | None] | None = None
    bookdepth: list[float | None] | None = None
```

- [ ] **Step 4: Register `ob_imbalance_follow` in entries.py**

In `src/moonface/research/entries.py`, add the import after the positioning import:
```python
from moonface.backtest.edge.ob_imbalance_signals import make_ob_imbalance_follow
```
Add a routing branch in `generate_entries` (before the `dsl_expr` branch):
```python
    if family == "ob_imbalance_follow":
        if bundle.bookdepth is None:
            raise ValueError(
                "ob_imbalance_follow requires bookdepth data in the bundle")
        return make_ob_imbalance_follow(bundle.bookdepth)(bundle.candles, params)
```
Add it to `known_families`:
```python
def known_families() -> set[str]:
    """Every family generate_entries can evaluate."""
    return (set(PRICE_FAMILIES) | set(_FUNDING_FAMILIES)
            | set(_POSITIONING_FAMILIES)
            | {"basis_discount_reversion", "eth_lead_momentum",
               "ob_imbalance_follow", "dsl_expr"})
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_multifamily_screen.py -q`
Expected: PASS.

- [ ] **Step 6: Run ruff and commit**

Run: `ruff check src/moonface/research/bundle.py src/moonface/research/entries.py tests/test_multifamily_screen.py`
Expected: no errors.
```bash
git add src/moonface/research/bundle.py src/moonface/research/entries.py tests/test_multifamily_screen.py
git commit -m "feat(entries): register ob_imbalance_follow + bookdepth bundle field"
```

---

## Task 4: Bundle-aware screening path in drift_screen

**Files:**
- Modify: `src/moonface/research/drift_screen.py` (add new functions; existing candles-only functions untouched)
- Test: `tests/test_multifamily_screen.py`

Add `score_family_on_asset` and `screen_family` that resolve events through `generate_entries(family, params, bundle)` and reuse `nonoverlap`, `event_outcome`, `asset_path_stats`, `drift_verdict`. The pool is `dict[str, DataBundle]`. The binding verdict uses a single `h` (the family's primary horizon).

- [ ] **Step 1: Write the failing tests (append to `tests/test_multifamily_screen.py`)**

```python
from moonface.research.drift_screen import score_family_on_asset, screen_family


class TestScreenFamily(unittest.TestCase):
    def _bid_drift_bundle(self):
        # 30 flat bars, then 20 up bars; positive imbalance spikes precede ups
        n = 50
        candles = [_c(i, 100.0) for i in range(30)] + [
            Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                   100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(20)]
        book = [0.0] * n
        for i in range(28, 48):           # strong bid imbalance before each up
            book[i] = 4.0
        return DataBundle(candles=candles, bookdepth=book)

    def test_score_family_on_asset_produces_stats(self):
        bundle = self._bid_drift_bundle()
        stats = score_family_on_asset("ob_imbalance_follow",
                                      {"window": 20, "z_thr": 1.0}, bundle,
                                      h=3, atr_period=14)
        self.assertGreaterEqual(stats["n"], 1)
        self.assertIn("mean_mfe_r", stats)
        self.assertIn("sign_rate", stats)

    def test_screen_family_renders_verdict_and_identity(self):
        pool = {f"A{j}": self._bid_drift_bundle() for j in range(9)}
        result = screen_family("ob_imbalance_follow",
                               {"window": 20, "z_thr": 1.0}, pool,
                               h=3, atr_period=14, floor=0.1,
                               min_events=1, min_assets=8)
        self.assertEqual(result["signal"], "ob_imbalance_follow")
        self.assertEqual(result["params"], {"window": 20, "z_thr": 1.0})
        self.assertEqual(result["h"], 3)
        self.assertIn(result["verdict"]["verdict"],
                      ("mechanism_exists", "mechanism_does_not_exist",
                       "inconclusive"))

    def test_asset_failing_family_data_is_dropped(self):
        pool = {f"A{j}": self._bid_drift_bundle() for j in range(8)}
        pool["NOBOOK"] = DataBundle(candles=[_c(i) for i in range(50)])
        result = screen_family("ob_imbalance_follow",
                               {"window": 20, "z_thr": 1.0}, pool,
                               h=3, atr_period=14, floor=0.1,
                               min_events=1, min_assets=8)
        self.assertNotIn("NOBOOK", [a["sym"] for a in result["assets"]])
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_multifamily_screen.py -q`
Expected: FAIL — `score_family_on_asset` / `screen_family` not defined.

- [ ] **Step 3: Implement the bundle-aware path**

In `src/moonface/research/drift_screen.py`, add at the top with the other imports:
```python
from moonface.research.bundle import DataBundle
from moonface.research.entries import generate_entries
```
Append these functions at the end of the module:
```python
def score_family_on_asset(family: str, params: dict, bundle: DataBundle,
                          h: int, atr_period: int) -> dict:
    """Bundle-aware sibling of score_signal_on_asset: resolve events through
    generate_entries (so funding/positioning/orderbook families work), drop
    serially-overlapping events, and return the per-asset path stats. An asset
    whose bundle lacks the family's required data raises inside generate_entries
    and is treated as zero-evidence by the caller."""
    events = nonoverlap(generate_entries(family, params, bundle), h)
    outcomes: list[tuple[float, float, float]] = []
    for i, side in events:
        out = event_outcome(bundle.candles, i, side, h, atr_period)
        if out is not None:
            outcomes.append(out)
    return asset_path_stats(outcomes)


def screen_family(family: str, params: dict,
                  pool: dict[str, DataBundle], h: int, atr_period: int,
                  floor: float, min_events: int = MIN_EVENTS_PER_ASSET,
                  min_assets: int = MIN_ASSETS) -> dict:
    """Screen one family across a per-asset DataBundle pool. Each asset with at
    least min_events non-overlapping tradeable events is one unit of evidence.
    An asset whose bundle lacks the family's data (generate_entries raises
    ValueError) contributes no evidence and is skipped."""
    per_asset: list[dict] = []
    for sym in sorted(pool):
        try:
            stats = score_family_on_asset(family, params, pool[sym], h,
                                           atr_period)
        except ValueError:
            continue
        if stats["n"] >= min_events:
            per_asset.append({"sym": sym, **stats})
    verdict = drift_verdict(per_asset, floor=floor, min_assets=min_assets)
    return {"signal": family, "params": params, "h": h,
            "assets": per_asset, "verdict": verdict}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_multifamily_screen.py tests/test_drift_screen.py -q`
Expected: PASS (new bundle path works; existing price path unchanged).

- [ ] **Step 5: Run ruff and commit**

Run: `ruff check src/moonface/research/drift_screen.py tests/test_multifamily_screen.py`
Expected: no errors.
```bash
git add src/moonface/research/drift_screen.py tests/test_multifamily_screen.py
git commit -m "feat(drift-screen): bundle-aware screen_family via generate_entries"
```

---

## Task 5: Multi-horizon descriptive curve

**Files:**
- Modify: `src/moonface/research/drift_screen.py` (add `horizon_curve`)
- Test: `tests/test_multifamily_screen.py`

`horizon_curve` computes per-horizon pooled descriptive stats (pooled ret_r, pooled sign_rate, pooled |MAE|, pooled MFE, Stouffer Z) over the pool for a list of horizons. It is descriptive only — it renders no PASS/FAIL and applies no floor.

- [ ] **Step 1: Write the failing test (append to `tests/test_multifamily_screen.py`)**

```python
from moonface.research.drift_screen import horizon_curve


class TestHorizonCurve(unittest.TestCase):
    def test_curve_has_one_row_per_horizon(self):
        pool = {f"A{j}": TestScreenFamily()._bid_drift_bundle()
                for j in range(9)}
        curve = horizon_curve("ob_imbalance_follow",
                              {"window": 20, "z_thr": 1.0}, pool,
                              horizons=[3, 6, 12], atr_period=14,
                              min_events=1, min_assets=8)
        self.assertEqual([row["h"] for row in curve], [3, 6, 12])
        for row in curve:
            self.assertIn("pooled_ret_r", row)
            self.assertIn("pooled_sign_rate", row)
            self.assertIn("pooled_abs_mae_r", row)
            self.assertIn("pooled_mfe_r", row)
            self.assertIn("stouffer_z", row)
            self.assertIn("m_assets", row)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_multifamily_screen.py::TestHorizonCurve -q`
Expected: FAIL — `horizon_curve` not defined.

- [ ] **Step 3: Implement `horizon_curve`**

Append to `src/moonface/research/drift_screen.py`:
```python
def horizon_curve(family: str, params: dict, pool: dict[str, DataBundle],
                  horizons: list[int], atr_period: int,
                  min_events: int = MIN_EVENTS_PER_ASSET,
                  min_assets: int = MIN_ASSETS) -> list[dict]:
    """Descriptive term structure: pooled stats at each horizon. NOT a gate —
    no floor, no PASS/FAIL. Renders evidence of drift shape/decay only. The
    binding verdict is screen_family at the frozen primary horizon."""
    rows: list[dict] = []
    for h in horizons:
        per_asset = []
        for sym in sorted(pool):
            try:
                s = score_family_on_asset(family, params, pool[sym], h,
                                          atr_period)
            except ValueError:
                continue
            if s["n"] >= min_events:
                per_asset.append(s)
        m = len(per_asset)
        if m < min_assets:
            rows.append({"h": h, "m_assets": m, "pooled_ret_r": None,
                         "pooled_sign_rate": None, "pooled_abs_mae_r": None,
                         "pooled_mfe_r": None, "stouffer_z": None})
            continue
        rows.append({
            "h": h, "m_assets": m,
            "pooled_ret_r": fmean([s["mean_ret_r"] for s in per_asset]),
            "pooled_sign_rate": fmean([s["sign_rate"] for s in per_asset]),
            "pooled_abs_mae_r": fmean([s["mean_abs_mae_r"] for s in per_asset]),
            "pooled_mfe_r": fmean([s["mean_mfe_r"] for s in per_asset]),
            "stouffer_z": stouffer([s["t"] for s in per_asset])})
    return rows
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_multifamily_screen.py::TestHorizonCurve -q`
Expected: PASS.

- [ ] **Step 5: Run ruff and commit**

Run: `ruff check src/moonface/research/drift_screen.py`
Expected: no errors.
```bash
git add src/moonface/research/drift_screen.py tests/test_multifamily_screen.py
git commit -m "feat(drift-screen): descriptive multi-horizon curve (no gate)"
```

---

## Task 6: Per-asset bundle loader for the 16-asset pool

**Files:**
- Create: `src/moonface/research/multifamily_loader.py`
- Test: `tests/test_multifamily_loader.py`

Assemble a `DataBundle` per pool symbol from cached CSVs: 4h candles + funding + one metrics field + bookdepth mean imbalance. Coverage is enforced by the downstream `min_events`/`min_assets` gate, but a symbol that cannot load candles at all is omitted from the pool. The loader takes injectable readers so tests need no network or disk.

The archive symbol for the metrics/bookdepth caches is the plain `BTCUSDT` form (no `/` or `:USDT`); the pool symbols are already in that form (e.g. `1000PEPEUSDT`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_multifamily_loader.py`:
```python
import unittest

from moonface.models import Candle
from moonface.research.multifamily_loader import load_pool_bundles

H4 = 4 * 3_600_000


def _candles(n):
    return [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(n)]


class TestLoadPoolBundles(unittest.TestCase):
    def _readers(self):
        candles = _candles(40)
        return {
            "candles": lambda sym, tf: candles,
            "funding": lambda sym: [0.01] * 40,
            "metrics": lambda sym, field: [5.0] * 40,
            "bookdepth": lambda sym: [0.5] * 40,
        }

    def test_builds_bundle_per_symbol(self):
        pool = load_pool_bundles(
            ["DOGEUSDT", "XRPUSDT"], metrics_field="sum_open_interest",
            **self._readers())
        self.assertEqual(set(pool), {"DOGEUSDT", "XRPUSDT"})
        b = pool["DOGEUSDT"]
        self.assertEqual(len(b.candles), 40)
        self.assertIsNotNone(b.funding)
        self.assertIsNotNone(b.feature)
        self.assertIsNotNone(b.bookdepth)

    def test_symbol_without_candles_is_omitted(self):
        readers = self._readers()
        readers["candles"] = lambda sym, tf: ([] if sym == "BAD"
                                              else _candles(40))
        pool = load_pool_bundles(["GOOD", "BAD"],
                                 metrics_field="sum_open_interest", **readers)
        self.assertIn("GOOD", pool)
        self.assertNotIn("BAD", pool)

    def test_missing_optional_series_left_none(self):
        readers = self._readers()
        readers["funding"] = lambda sym: None
        readers["bookdepth"] = lambda sym: None
        pool = load_pool_bundles(["DOGEUSDT"],
                                 metrics_field="sum_open_interest", **readers)
        b = pool["DOGEUSDT"]
        self.assertIsNone(b.funding)
        self.assertIsNone(b.bookdepth)
        self.assertIsNotNone(b.feature)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_multifamily_loader.py -q`
Expected: FAIL — module `multifamily_loader` does not exist.

- [ ] **Step 3: Implement the loader with injectable readers**

Create `src/moonface/research/multifamily_loader.py`:
```python
"""Per-asset DataBundle loader for the multi-family drift screen's 16-asset 4h
pool. Each bundle carries candles + funding + one metrics field + per-bar mean
bookdepth imbalance, all aligned 1:1 with candles. Readers are injectable so
tests run with no network or disk; the default readers wire the existing CSV
caches."""
from __future__ import annotations

from collections.abc import Callable

from moonface.models import Candle
from moonface.research.bundle import DataBundle

CandleReader = Callable[[str, str], "list[Candle]"]
FundingReader = Callable[[str], "list[float | None] | None"]
MetricsReader = Callable[[str, str], "list[float | None] | None"]
BookdepthReader = Callable[[str], "list[float | None] | None"]


def load_pool_bundles(symbols: list[str], metrics_field: str,
                      candles: CandleReader, funding: FundingReader,
                      metrics: MetricsReader,
                      bookdepth: BookdepthReader,
                      timeframe: str = "4h") -> dict[str, DataBundle]:
    """Build {symbol: DataBundle} for the pool. A symbol whose candle reader
    returns nothing is omitted (no price series to score against). Optional
    series (funding/metrics/bookdepth) that return None are left None; the
    family generators raise on missing data and the screen drops that asset for
    that family."""
    pool: dict[str, DataBundle] = {}
    for sym in symbols:
        bars = candles(sym, timeframe)
        if not bars:
            continue
        pool[sym] = DataBundle(
            candles=bars,
            funding=funding(sym),
            feature=metrics(sym, metrics_field),
            bookdepth=bookdepth(sym))
    return pool
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_multifamily_loader.py -q`
Expected: PASS.

- [ ] **Step 5: Run ruff and commit**

Run: `ruff check src/moonface/research/multifamily_loader.py tests/test_multifamily_loader.py`
Expected: no errors.
```bash
git add src/moonface/research/multifamily_loader.py tests/test_multifamily_loader.py
git commit -m "feat(multifamily): per-asset DataBundle pool loader (injectable readers)"
```

---

## Task 7: Default cache-backed readers for the loader

**Files:**
- Modify: `src/moonface/research/multifamily_loader.py` (add `default_readers`)
- Test: `tests/test_multifamily_loader.py`

Provide concrete readers wiring the existing caches: `OhlcvCache.load` for candles, `FundingCache`/`align_funding` for funding, `metrics_data` for the metrics field, `bookdepth_data` + `bar_mean_imbalance` for imbalance. Each optional reader returns None on any failure (missing cache file) so a partial family still screens on the assets that do have data.

- [ ] **Step 1: Write the failing test (append to `tests/test_multifamily_loader.py`)**

```python
from moonface.research.multifamily_loader import default_readers


class TestDefaultReaders(unittest.TestCase):
    def test_returns_four_callables(self):
        r = default_readers(cache_dir=".backtest_cache",
                            start_ms=0, end_ms=H4 * 10)
        for key in ("candles", "funding", "metrics", "bookdepth"):
            self.assertTrue(callable(r[key]))

    def test_optional_readers_swallow_missing_files(self):
        r = default_readers(cache_dir="/tmp/does-not-exist-xyz",
                            start_ms=0, end_ms=H4 * 10)
        # missing cache dir -> optional readers return None, never raise
        self.assertIsNone(r["funding"]("NOPEUSDT"))
        self.assertIsNone(r["metrics"]("NOPEUSDT", "sum_open_interest"))
        self.assertIsNone(r["bookdepth"]("NOPEUSDT"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_multifamily_loader.py::TestDefaultReaders -q`
Expected: FAIL — `default_readers` not defined.

- [ ] **Step 3: Implement `default_readers`**

Append to `src/moonface/research/multifamily_loader.py`:
```python
def default_readers(cache_dir: str, start_ms: int, end_ms: int) -> dict:
    """Concrete readers over the existing CSV caches. Candle reader uses
    OhlcvCache.load; optional readers swallow missing-file errors and return
    None so a family still screens on the assets that do have its data.
    Imbalance is aggregated to per-bar means via bar_mean_imbalance."""
    from moonface.backtest.bookdepth_data import (fetch_bookdepth_history,
                                                  imbalance_points)
    from moonface.backtest.data import OhlcvCache
    from moonface.backtest.edge.funding import (FundingCache, align_funding,
                                                fetch_funding_history)
    from moonface.backtest.edge.ob_imbalance_signals import bar_mean_imbalance
    from moonface.backtest.metrics_data import (align_metric,
                                                fetch_metrics_history)

    ohlcv = OhlcvCache(cache_dir)

    def candles(sym, tf):
        bars = ohlcv.load(sym, tf)
        return bars or []

    def funding(sym):
        try:
            pts = fetch_funding_history("binance", sym, start_ms, end_ms,
                                        FundingCache(cache_dir))
            return align_funding(ohlcv.load(sym, "4h") or [], pts)
        except Exception:
            return None

    def metrics(sym, field):
        try:
            raw = fetch_metrics_history(sym, start_ms, end_ms, cache_dir)
            return align_metric(ohlcv.load(sym, "4h") or [],
                                [(ts, f[field]) for ts, f in raw if field in f])
        except Exception:
            return None

    def bookdepth(sym):
        try:
            rows = fetch_bookdepth_history(sym, start_ms, end_ms, cache_dir)
            return bar_mean_imbalance(ohlcv.load(sym, "4h") or [],
                                      imbalance_points(rows))
        except Exception:
            return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}
```

**Note for the implementer:** confirm the funding cache symbol form `fetch_funding_history` expects matches the pool symbol form (`DOGEUSDT`) before the real run; if the funding cache keys on `DOGE/USDT:USDT`, map inside the `funding` reader. This only affects the live run (Task 9), not the unit tests.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_multifamily_loader.py -q`
Expected: PASS.

- [ ] **Step 5: Run ruff and commit**

Run: `ruff check src/moonface/research/multifamily_loader.py`
Expected: no errors.
```bash
git add src/moonface/research/multifamily_loader.py tests/test_multifamily_loader.py
git commit -m "feat(multifamily): default cache-backed readers for the pool loader"
```

---

## Task 8: CLI — phase-a (per-horizon floor), register, run

**Files:**
- Create: `tools/drift_screen_multifamily.py`
- Test: `tests/test_drift_screen_multifamily_cli.py`

Mirror `tools/drift_screen.py` but: (a) `phase-a` recalibrates the floor at a **given horizon** from the existing edge/positioning result files, reusing `drift_screen`'s `compute_floor_from_rows`/`load_*_rows`; (b) the registry is the three families with their frozen per-family primary horizons and params; (c) `run` builds the pool via `multifamily_loader`, screens each family at its primary horizon with the matching frozen floor, attaches the descriptive `horizon_curve`, and writes a leaderboard.

Frozen registry (signals + per-family primary horizon `h` in 4h bars):
```python
FAMILIES = [
    {"family": "funding_fade",         "params": {"window": 60, "z_thr": 1.5},  "h": 6},
    {"family": "funding_confirm",      "params": {"window": 60, "z_thr": 1.5},  "h": 6},
    {"family": "funding_flip",         "params": {"debounce": 6},               "h": 6},
    {"family": "oi_build_momentum",    "params": {"window": 180, "lookback": 6, "z_thr": 1.5}, "h": 6},
    {"family": "oi_flush_reversal",    "params": {"window": 180, "lookback": 6, "z_thr": 1.5}, "h": 6},
    {"family": "toptrader_follow",     "params": {"window": 180, "z_thr": 1.5}, "h": 6},
    {"family": "taker_flow_momentum",  "params": {"window": 180, "z_thr": 1.5}, "h": 6},
    {"family": "ob_imbalance_follow",  "params": {"window": 180, "z_thr": 1.5}, "h": 3},
    {"family": "ob_imbalance_follow",  "params": {"window": 180, "z_thr": 2.0}, "h": 3},
]
```

Each family's metrics field for the bundle (funding/orderbook families ignore it; positioning families need it):
```python
METRICS_FIELD = {
    "oi_build_momentum": "sum_open_interest",
    "oi_flush_reversal": "sum_open_interest",
    "toptrader_follow": "sum_toptrader_long_short_ratio",
    "taker_flow_momentum": "sum_taker_long_short_vol_ratio",
}
```
Because positioning families need different metrics fields, the pool is built **per metrics field** lazily and cached, or the run loads each family's pool on demand. The plan builds one pool per distinct metrics field (`sum_open_interest`, `sum_toptrader_long_short_ratio`, `sum_taker_long_short_vol_ratio`) plus one field-agnostic pool for funding/orderbook (any field works since they ignore `feature`).

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/test_drift_screen_multifamily_cli.py`:
```python
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.models import Candle

import importlib.util
import sys

_CLI = Path(__file__).resolve().parents[1] / "tools" / "drift_screen_multifamily.py"
_spec = importlib.util.spec_from_file_location("dsm_cli", _CLI)
dsm = importlib.util.module_from_spec(_spec)
sys.modules["dsm_cli"] = dsm
_spec.loader.exec_module(dsm)

H4 = 4 * 3_600_000


class TestPhaseA(unittest.TestCase):
    def test_floor_at_horizon_from_dead_rows(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            pos = out / "pos.json"
            edge = out / "edge.json"
            pos.write_text(json.dumps(
                [{"oos_expectancy_r": 0.5, "research_max_dd_r": -10.0}]))
            edge.write_text(json.dumps(
                [{"horizon_oos_expectancy_r": 1.0, "bracket_net_r": -8.0}]))
            floor = dsm.cmd_phase_a(out, positioning=pos, edge=edge, h=3)
            # largest ratio among dead rows: max(0.5/10, 1.0/8) = 0.125
            self.assertAlmostEqual(floor, 0.125, places=4)
            self.assertTrue((out / "phaseA_gap_h3.md").exists())


class TestRegisterAndRun(unittest.TestCase):
    def _pool_readers(self):
        n = 60
        flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(30)]
        up = [Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                     100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(30)]
        bars = flat + up
        book = [0.0] * n
        for i in range(28, 58):
            book[i] = 4.0
        return {
            "candles": lambda sym, tf: bars,
            "funding": lambda sym: [0.01] * n,
            "metrics": lambda sym, field: [5.0 + (i % 3) for i in range(n)],
            "bookdepth": lambda sym: book,
        }

    def test_register_then_run_writes_leaderboard(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            dsm.cmd_register(out, floors={"3": 0.1, "6": 0.1319})
            self.assertTrue((out / "registration.json").exists())
            dsm.cmd_run(out, readers=self._pool_readers(),
                        symbols=[f"A{j}" for j in range(9)])
            lb = json.loads((out / "leaderboard.json").read_text())
            self.assertEqual(len(lb), len(dsm.FAMILIES))
            for row in lb:
                self.assertIn("verdict", row)
                self.assertIn("curve", row)            # descriptive curve attached
                self.assertIn(row["verdict"]["verdict"],
                              ("mechanism_exists", "mechanism_does_not_exist",
                               "inconclusive"))

    def test_register_is_frozen(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            dsm.cmd_register(out, floors={"3": 0.1, "6": 0.1319})
            with self.assertRaises(SystemExit):
                dsm.cmd_register(out, floors={"3": 0.2, "6": 0.2})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_drift_screen_multifamily_cli.py -q`
Expected: FAIL — `tools/drift_screen_multifamily.py` does not exist.

- [ ] **Step 3: Implement the CLI**

Create `tools/drift_screen_multifamily.py`:
```python
#!/usr/bin/env python
# tools/drift_screen_multifamily.py
"""Multi-family exit-free drift screen CLI.

phase-a : recalibrate the path-ratio floor AT A GIVEN HORIZON from the existing
          edge/positioning result files (the same known-dead evidence the
          original floor used). Run once per primary horizon (h=3, h=6).
register: freeze the design — families, per-family primary horizons, params,
          and the per-horizon floors.
run     : build the 16-asset 4h pool (candles + funding + metrics + bookdepth),
          screen each family at its primary horizon under the path-aware gate,
          attach the descriptive multi-horizon curve, write the leaderboard.

Mechanism science only: no exits, stops, TPs, or grids. Per-family primary
horizon for PASS/FAIL; all other horizons are descriptive.
Design frozen in experiments/drift_screen_multifamily/PREREGISTRATION.md."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.drift_screen import horizon_curve, screen_family
from moonface.research.multifamily_loader import (default_readers,
                                                  load_pool_bundles)
# Reuse the price screen's floor calibration helpers verbatim.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_screen import (compute_floor_from_rows, load_edge_rows,  # noqa: E402
                          load_positioning_rows)

UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT"]
DISCOVERY = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

FAMILIES = [
    {"family": "funding_fade",        "params": {"window": 60, "z_thr": 1.5},  "h": 6},
    {"family": "funding_confirm",     "params": {"window": 60, "z_thr": 1.5},  "h": 6},
    {"family": "funding_flip",        "params": {"debounce": 6},               "h": 6},
    {"family": "oi_build_momentum",   "params": {"window": 180, "lookback": 6, "z_thr": 1.5}, "h": 6},
    {"family": "oi_flush_reversal",   "params": {"window": 180, "lookback": 6, "z_thr": 1.5}, "h": 6},
    {"family": "toptrader_follow",    "params": {"window": 180, "z_thr": 1.5}, "h": 6},
    {"family": "taker_flow_momentum", "params": {"window": 180, "z_thr": 1.5}, "h": 6},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 1.5}, "h": 3},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 2.0}, "h": 3},
]

METRICS_FIELD = {
    "oi_build_momentum": "sum_open_interest",
    "oi_flush_reversal": "sum_open_interest",
    "toptrader_follow": "sum_toptrader_long_short_ratio",
    "taker_flow_momentum": "sum_taker_long_short_vol_ratio",
}
DEFAULT_FIELD = "sum_open_interest"  # funding/orderbook families ignore feature

CURVE_HORIZONS = [3, 6, 12, 18, 24]   # 12h,24h,48h,72h,96h (4h bars; 6h sub-bar)
ATR_PERIOD = 14
MIN_EVENTS = 10
MIN_ASSETS = 8

DESIGN = {"timeframe": "4h", "atr_period": ATR_PERIOD, "min_events": MIN_EVENTS,
          "min_assets": MIN_ASSETS, "universe": UNIVERSE, "discovery": DISCOVERY,
          "families": FAMILIES, "curve_horizons": CURVE_HORIZONS}


def _read_json(path: Path):
    return json.loads(path.read_text())


def cmd_phase_a(out_dir: Path, positioning: Path, edge: Path, h: int) -> float:
    """Floor recalibrated at horizon h. The dead-row ratios are horizon-
    agnostic R magnitudes from the prior result files; this re-derives the bar
    so it is frozen per primary horizon rather than reused from h=24."""
    dead = (load_positioning_rows(_read_json(positioning))
            + load_edge_rows(_read_json(edge)))
    floor = compute_floor_from_rows(dead)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Multi-family drift screen — Phase A floor at h={h}", "",
             f"- known-dead drifting rows: {len(dead)}",
             f"- **calibrated floor (ret_r/|mae_r|) at h={h}: {floor:.4f}**", ""]
    (out_dir / f"phaseA_gap_h{h}.md").write_text("\n".join(lines) + "\n")
    return floor


def cmd_register(out_dir: Path, floors: dict) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    reg = dict(DESIGN)
    reg["floors"] = floors          # {"3": <h3 floor>, "6": <h6 floor>}
    reg["registered_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} ({len(FAMILIES)} families, floors={floors})")


def cmd_run(out_dir: Path, readers: dict | None = None,
            symbols: list[str] | None = None,
            cache_dir: str = ".backtest_cache") -> None:
    reg = json.loads((out_dir / "registration.json").read_text())
    symbols = symbols or reg["universe"]
    if readers is None:
        # 3 years of 4h history; the caches already span it.
        end_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)

    # One pool per distinct metrics field (positioning families differ); funding
    # and orderbook families ignore `feature`, so they reuse the default-field
    # pool. Build lazily and cache.
    pools: dict[str, dict] = {}

    def pool_for(field: str):
        if field not in pools:
            pools[field] = load_pool_bundles(
                symbols, metrics_field=field, **readers)
        return pools[field]

    results = []
    for spec in reg["families"]:
        fam, params, h = spec["family"], spec["params"], spec["h"]
        field = METRICS_FIELD.get(fam, DEFAULT_FIELD)
        pool = pool_for(field)
        floor = reg["floors"][str(h)]
        res = screen_family(fam, params, pool, h=h, atr_period=reg["atr_period"],
                            floor=floor, min_events=reg["min_events"],
                            min_assets=reg["min_assets"])
        res["curve"] = horizon_curve(fam, params, pool,
                                     horizons=reg["curve_horizons"],
                                     atr_period=reg["atr_period"],
                                     min_events=reg["min_events"],
                                     min_assets=reg["min_assets"])
        results.append(res)

    results.sort(key=lambda r: -1.0 if r["verdict"]["ratio"] is None
                 else r["verdict"]["ratio"], reverse=True)
    (out_dir / "leaderboard.json").write_text(json.dumps(results, indent=2))
    (out_dir / "leaderboard.md").write_text(_render_md(results))
    print(f"screened {len(results)} families -> {out_dir / 'leaderboard.md'}")


def _f(x) -> str:
    return "" if x is None else f"{x:.4f}"


def _render_md(results: list[dict]) -> str:
    lines = ["# Multi-family drift screen — leaderboard", "",
             "| family | params | h | m | p_sign | Z | pooled_ret_r "
             "| pooled_|mae|_r | pooled_mfe_r | sign_rate | ratio | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        v = r["verdict"]
        sr = (sum(a["sign_rate"] for a in r["assets"]) / len(r["assets"])
              if r["assets"] else None)
        mfe = (sum(a["mean_mfe_r"] for a in r["assets"]) / len(r["assets"])
               if r["assets"] else None)
        lines.append(
            f"| {r['signal']} | {r['params']} | {r['h']} | {v['m_assets']} "
            f"| {_f(v['p_sign'])} | {_f(v['stouffer_z'])} "
            f"| {_f(v['pooled_ret_r'])} | {_f(v['pooled_abs_mae_r'])} "
            f"| {_f(mfe)} | {_f(sr)} | {_f(v['ratio'])} | {v['verdict']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="multi-family drift screen")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("phase-a", help="calibrate floor at one horizon")
    pa.add_argument("--positioning", type=Path, required=True)
    pa.add_argument("--edge", type=Path, required=True)
    pa.add_argument("--h", type=int, required=True)
    pa.add_argument("--out", type=Path,
                    default=Path("experiments/drift_screen_multifamily"))

    pr = sub.add_parser("register", help="freeze design + per-horizon floors")
    pr.add_argument("--floor-h3", type=float, required=True)
    pr.add_argument("--floor-h6", type=float, required=True)
    pr.add_argument("--out", type=Path,
                    default=Path("experiments/drift_screen_multifamily"))

    rn = sub.add_parser("run", help="screen all families -> leaderboard")
    rn.add_argument("--out", type=Path,
                    default=Path("experiments/drift_screen_multifamily"))

    args = parser.parse_args(argv)
    if args.cmd == "phase-a":
        floor = cmd_phase_a(args.out, positioning=args.positioning,
                            edge=args.edge, h=args.h)
        print(f"calibrated floor at h={args.h}: {floor:.4f}")
    elif args.cmd == "register":
        cmd_register(args.out, floors={"3": args.floor_h3, "6": args.floor_h6})
    elif args.cmd == "run":
        cmd_run(args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_drift_screen_multifamily_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Run ruff and the full suite, then commit**

Run: `ruff check tools/drift_screen_multifamily.py tests/test_drift_screen_multifamily_cli.py`
Run: `pytest -q`
Expected: ruff clean; full suite green.
```bash
git add tools/drift_screen_multifamily.py tests/test_drift_screen_multifamily_cli.py
git commit -m "feat(drift-screen): multi-family CLI (per-horizon floor, descriptive curve)"
```

---

## Task 9: Freeze the pre-registration and run the screen

**Files:**
- Create: `experiments/drift_screen_multifamily/PREREGISTRATION.md`
- Create (generated): `experiments/drift_screen_multifamily/{phaseA_gap_h3.md, phaseA_gap_h6.md, registration.json, leaderboard.json, leaderboard.md}`

This task runs the real calibration and screen. It is mechanical — no tuning. Floors come out of phase-a; the pre-registration freezes them before `run`.

- [ ] **Step 1: Locate the known-dead result files used by the original floor**

Run: `ls experiments/positioning_exits/ experiments/edge/`
Find the positioning-exit result JSON and the edge leaderboard JSON the original `experiments/drift_screen/PREREGISTRATION.md` cited (the same files `tools/drift_screen.py phase-a` consumed). Record their paths.

- [ ] **Step 2: Recalibrate the floor at h=6 and h=3**

Run (substitute the real paths from Step 1):
```bash
python tools/drift_screen_multifamily.py phase-a \
  --positioning <pos.json> --edge <edge.json> --h 6
python tools/drift_screen_multifamily.py phase-a \
  --positioning <pos.json> --edge <edge.json> --h 3
```
Expected: prints `calibrated floor at h=6: <F6>` and `calibrated floor at h=3: <F3>`, writes `phaseA_gap_h6.md` and `phaseA_gap_h3.md`. The h=6 floor should reproduce `0.1319` (same evidence as the original h=24 calibration; the dead-row ratios are horizon-agnostic R magnitudes). Note both values.

- [ ] **Step 3: Write the pre-registration freezing the design and both floors**

Create `experiments/drift_screen_multifamily/PREREGISTRATION.md` with: the 16-asset universe and excluded discovery set (copy from `experiments/drift_screen/PREREGISTRATION.md`); the three families and the nine frozen `(family, params, primary horizon)` rows from `FAMILIES`; the descriptive horizon set `{3,6,12,18,24}`; the recalibrated floors `F3`/`F6` from Step 2; the MAE/MFE/sign-rate conventions; and the frozen statement that no exits/stops/TPs/grids are fit and the orderbook definition is not tuned after results. Use `experiments/drift_screen/PREREGISTRATION.md` as the structural template.

- [ ] **Step 4: Register (freeze) then run**

Run (substitute `F3`/`F6` from Step 2):
```bash
python tools/drift_screen_multifamily.py register --floor-h3 <F3> --floor-h6 <F6>
python tools/drift_screen_multifamily.py run
```
Expected: `registration.json` written then frozen; `run` prints `screened 9 families -> .../leaderboard.md` and writes `leaderboard.json` + `leaderboard.md`.

- [ ] **Step 5: Sanity-check the leaderboard**

Run: `cat experiments/drift_screen_multifamily/leaderboard.md`
Expected: nine rows (one per `FAMILIES` entry), each with a tripartite verdict, a path ratio vs the horizon-matched floor, and the pooled MFE/sign-rate columns. `m` (assets) should be ≥ 8 for families whose data covers the pool; a family with sparse data may show fewer and read `inconclusive`.

- [ ] **Step 6: Commit the frozen artifacts**

```bash
git add -f experiments/drift_screen_multifamily/PREREGISTRATION.md \
  experiments/drift_screen_multifamily/phaseA_gap_h3.md \
  experiments/drift_screen_multifamily/phaseA_gap_h6.md \
  experiments/drift_screen_multifamily/registration.json \
  experiments/drift_screen_multifamily/leaderboard.json \
  experiments/drift_screen_multifamily/leaderboard.md
git commit -m "feat(drift-screen): freeze multi-family pre-registration + run verdict"
```

**Note:** `experiments/` may be partly gitignored (the global `.gitignore_global` ignores `docs/`; check `git check-ignore` for these paths and use `git add -f` as needed, matching how prior pre-registrations were committed).

---

## Task 10: README + final verification

**Files:**
- Modify: `README.md` (document the new CLI alongside the existing drift-screen entry)

- [ ] **Step 1: Document the multi-family CLI in the README**

Add a subsection near the existing drift-screen documentation describing the three commands (`phase-a --h`, `register --floor-h3 --floor-h6`, `run`), the three families covered, the per-family primary horizons (orderbook h=3, funding/OI h=6), the descriptive curve, and that it is exit-free. Match the surrounding README style.

- [ ] **Step 2: Run the full suite and ruff**

Run: `pytest -q && ruff check src tools tests`
Expected: all tests pass, ruff clean.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): document the multi-family drift screen CLI"
```

---

## Self-Review Notes

- **Spec coverage:** funding + OI + orderbook families (Tasks 2,3,8); bundle-aware generators via `generate_entries` while preserving the candles-only price path — new `screen_family` is additive, existing `screen_signal` untouched (Task 4); MFE + per-event sign rate (Task 1); descriptive curve at `{3,6,12,18,24}` (Task 5); per-family frozen primary horizons orderbook=3 / funding,OI=6 (Task 8 `FAMILIES`); per-horizon floor recalibration frozen before the run (Tasks 8,9); exit-free throughout (no exit/stop/TP/grid code anywhere). Basis/lead-lag/liquidations/cross-exchange excluded (not in `FAMILIES`). All spec sections map to a task.
- **Type consistency:** `event_outcome -> (ret_r, mae_r, mfe_r)` 3-tuple is used consistently in `asset_path_stats`, `score_signal_on_asset`, and `score_family_on_asset`. `asset_path_stats` keys (`mean_ret_r`, `mean_abs_mae_r`, `mean_mfe_r`, `sign_rate`, `t`, `n`) are consumed identically in `screen_family`, `horizon_curve`, and the CLI renderer. `DataBundle.bookdepth` is set by the loader and read by `entries.generate_entries`. `screen_family` returns the same `{signal, params, h, assets, verdict}` shape as `screen_signal` plus `curve` is attached by the CLI.
- **No placeholders:** every code step shows complete code; the one runtime unknown (funding cache symbol form) is flagged as a Task 7 implementer note and a Task 9 step, not left in code as a TODO.
