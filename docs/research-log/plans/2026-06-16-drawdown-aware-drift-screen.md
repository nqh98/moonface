# Drawdown-Aware Drift Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an exit-free, path-aware (MAE-penalized, R-unit) cross-asset mechanism screen that re-scores the existing signal registry on fresh assets, settling whether the program's "drawdown wall" is structural or a metric artifact of scoring mean return only.

**Architecture:** Pure stats live in `src/moonface/research/drift_screen.py`, generalizing `oibuild_study.py` (per-asset = one unit of evidence; sign test + Stouffer Z; tripartite verdict) and adding a per-event MAE-in-R measure plus a two-part gate. A thin CLI in `tools/drift_screen.py` mirrors `tools/oibuild_study.py`'s `register`/`run` shape, loading 4h candles from `.backtest_cache` via the existing `OhlcvCache`. Phase A is a one-off analysis script that calibrates the floor from existing result files before any pre-registration is frozen.

**Tech Stack:** Python 3.12, stdlib only (`statistics`, `math`, `csv`, `argparse`, `unittest`), reusing `moonface.backtest.edge` signals, `moonface.backtest.edge.evaluate._risk`, `moonface.backtest.data.OhlcvCache`, and `moonface.research.oibuild_study` statistics.

**Spec:** `docs/research-log/specs/2026-06-16-drawdown-aware-drift-screen-design.md`

---

## File Structure

- Create: `src/moonface/research/drift_screen.py` — pure path-aware outcome + gate + verdict. No IO.
- Create: `tests/test_drift_screen.py` — unit tests for the pure module (synthetic series).
- Create: `tools/drift_screen.py` — CLI: `phase-a`, `register`, `run`. Loads candles, runs signals, writes reports.
- Create: `tests/test_drift_screen_cli.py` — CLI-level tests (register freezes; run produces verdict on synthetic loaders).
- Create (by `phase-a` run, committed): `experiments/drift_screen/phaseA_gap.md` — descriptive gap report + chosen floor.
- Create (by `register`, committed): `experiments/drift_screen/PREREGISTRATION.md`, `registration.json`.
- Create (by `run`): `experiments/drift_screen/leaderboard.{md,json}`.

Reused (do not modify):
- `src/moonface/backtest/edge/evaluate.py::_risk` — ATR-at-entry R denominator.
- `src/moonface/backtest/edge/signals.py` — signal generators `(h1, params) -> list[(i, side)]`.
- `src/moonface/backtest/data.py::OhlcvCache` — headerless OHLCV CSV loader.
- `src/moonface/research/oibuild_study.py::{nonoverlap, binom_p_geq, stouffer, asset_stats}`.

---

## Task 1: Per-event path-aware outcome (`ret_r`, `mae_r`)

**Files:**
- Create: `src/moonface/research/drift_screen.py`
- Test: `tests/test_drift_screen.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drift_screen.py
import unittest

from moonface.models import Candle
from moonface.research.drift_screen import event_outcome

H4 = 4 * 3_600_000


def _candle(i, o, h, l, c):
    return Candle(i * H4, o, h, l, c, 1000.0)


class TestEventOutcome(unittest.TestCase):
    def test_long_drift_no_adverse_excursion(self):
        # flat-then-up, never trades below entry close (100) -> mae_r == 0
        candles = [_candle(0, 100, 100, 100, 100)] + [
            _candle(i, 100 + i, 100 + i, 100 + i, 100 + i) for i in range(1, 6)
        ]
        # atr over [0..i] is ~1.0 after warmup; use atr_period=2, h=3
        out = event_outcome(candles, i=2, side="LONG", h=3, atr_period=2)
        self.assertIsNotNone(out)
        ret_r, mae_r = out
        self.assertGreater(ret_r, 0.0)
        self.assertEqual(mae_r, 0.0)

    def test_long_drift_with_midhorizon_dip(self):
        # entry close 100, dips to low 90 mid-horizon, recovers to 106
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry bar i=2, close 100
            _candle(3, 100, 102, 90, 95),    # adverse: low 90
            _candle(4, 95, 107, 95, 106),
            _candle(5, 106, 107, 105, 106),
        ]
        out = event_outcome(candles, i=2, side="LONG", h=2, atr_period=2)
        self.assertIsNotNone(out)
        ret_r, mae_r = out
        self.assertGreater(ret_r, 0.0)       # closed up at i+2
        self.assertLess(mae_r, 0.0)          # lived through a drawdown
        # mae_r is (90 - 100)/atr_unit; ret_r is (106 - 100)/atr_unit
        self.assertAlmostEqual(ret_r / -mae_r, 6.0 / 10.0, places=4)

    def test_short_uses_high_for_adverse(self):
        # SHORT entry close 100; price spikes high 110 against, closes 94
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry i=2
            _candle(3, 100, 110, 100, 96),   # adverse high 110
            _candle(4, 96, 97, 93, 94),
        ]
        out = event_outcome(candles, i=2, side="SHORT", h=2, atr_period=2)
        ret_r, mae_r = out
        self.assertGreater(ret_r, 0.0)       # short profited (price fell)
        self.assertLess(mae_r, 0.0)
        # adverse = (close - high)/unit = (100 - 110)/unit ; ret = (100-94)/unit
        self.assertAlmostEqual(ret_r / -mae_r, 6.0 / 10.0, places=4)

    def test_untradeable_entry_returns_none(self):
        candles = [_candle(i, 100, 100, 100, 100) for i in range(4)]
        # zero ATR -> _risk None -> outcome None
        self.assertIsNone(event_outcome(candles, i=1, side="LONG", h=2, atr_period=2))

    def test_insufficient_future_bars_returns_none(self):
        candles = [_candle(i, 100, 101, 99, 100 + i) for i in range(4)]
        # i + h beyond series
        self.assertIsNone(event_outcome(candles, i=3, side="LONG", h=5, atr_period=2))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen.py -v`
Expected: FAIL with `ImportError: cannot import name 'event_outcome'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/research/drift_screen.py
"""Exit-free, path-aware cross-asset mechanism screen — pure statistics.

Generalizes oibuild_study with a per-event maximum adverse excursion (MAE)
measured in R (excursion / ATR-at-entry), so directional drift is judged
against the drawdown it lived through. No exits, stops, TPs, or grids: a
single fixed horizon h. Design frozen in
experiments/drift_screen/PREREGISTRATION.md."""
from __future__ import annotations

from moonface.backtest.edge.evaluate import _risk
from moonface.models import Candle


def event_outcome(candles: list[Candle], i: int, side: str, h: int,
                  atr_period: int) -> tuple[float, float] | None:
    """Per-event (ret_r, mae_r) in R units over a fixed horizon h.

    ret_r = side * (close[i+h] - close[i]) / unit   (forward move in R)
    mae_r = worst intra-horizon excursion AGAINST the position, in R, <= 0,
            using bar.low for LONG and bar.high for SHORT (the _fill
            convention). Returns None when the entry is untradeable (unit
            None) or there are fewer than h future bars."""
    unit = _risk(candles, i, 1.0, atr_period)
    if unit is None or i + h >= len(candles):
        return None
    entry = candles[i].close
    sign = 1.0 if side == "LONG" else -1.0
    ret_r = sign * (candles[i + h].close - entry) / unit
    worst = 0.0
    for k in range(1, h + 1):
        bar = candles[i + k]
        adverse = (bar.low - entry) if side == "LONG" else (entry - bar.high)
        excursion = adverse / unit
        if excursion < worst:
            worst = excursion
    return ret_r, worst
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/drift_screen.py tests/test_drift_screen.py
git commit -m "feat(drift-screen): per-event path-aware outcome (ret_r, mae_r) in R"
```

---

## Task 2: Per-asset path stats

**Files:**
- Modify: `src/moonface/research/drift_screen.py`
- Test: `tests/test_drift_screen.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen.py
from moonface.research.drift_screen import asset_path_stats


class TestAssetPathStats(unittest.TestCase):
    def test_aggregates_ret_and_mae(self):
        outcomes = [(2.0, -1.0), (4.0, -3.0), (3.0, -2.0)]
        s = asset_path_stats(outcomes)
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["mean_ret_r"], 3.0)
        self.assertAlmostEqual(s["mean_abs_mae_r"], 2.0)
        # t-stat of ret_r series is well-defined (nonzero variance)
        self.assertGreater(s["t"], 0.0)

    def test_empty_is_zeroed(self):
        s = asset_path_stats([])
        self.assertEqual(s["n"], 0)
        self.assertEqual(s["mean_ret_r"], 0.0)
        self.assertEqual(s["mean_abs_mae_r"], 0.0)
        self.assertEqual(s["t"], 0.0)

    def test_t_matches_oibuild_asset_stats(self):
        # ret_r series must reuse oibuild's t-stat definition exactly
        from moonface.research.oibuild_study import asset_stats
        outcomes = [(2.0, -1.0), (4.0, -3.0), (3.0, -2.0), (1.0, -0.5)]
        rets = [r for r, _ in outcomes]
        self.assertAlmostEqual(asset_path_stats(outcomes)["t"],
                               asset_stats(rets)["t"], places=10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen.py::TestAssetPathStats -v`
Expected: FAIL with `ImportError: cannot import name 'asset_path_stats'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/moonface/research/drift_screen.py
from statistics import fmean

from moonface.research.oibuild_study import asset_stats


def asset_path_stats(outcomes: list[tuple[float, float]]) -> dict:
    """One asset's evidence: mean forward R, mean absolute adverse R, and the
    ret_r t-stat (reusing oibuild's asset_stats so the magnitude test is
    identical across studies)."""
    if not outcomes:
        return {"n": 0, "mean_ret_r": 0.0, "mean_abs_mae_r": 0.0, "t": 0.0}
    rets = [r for r, _ in outcomes]
    maes = [abs(m) for _, m in outcomes]
    base = asset_stats(rets)
    return {"n": base["n"], "mean_ret_r": base["mean"],
            "mean_abs_mae_r": fmean(maes), "t": base["t"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen.py::TestAssetPathStats -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/drift_screen.py tests/test_drift_screen.py
git commit -m "feat(drift-screen): per-asset path stats reusing oibuild t-stat"
```

---

## Task 3: Two-part pooled verdict

**Files:**
- Modify: `src/moonface/research/drift_screen.py`
- Test: `tests/test_drift_screen.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen.py
from moonface.research.drift_screen import drift_verdict


def _stats(mean_ret, mean_abs_mae, t, n=30):
    return {"n": n, "mean_ret_r": mean_ret, "mean_abs_mae_r": mean_abs_mae, "t": t}


class TestDriftVerdict(unittest.TestCase):
    def test_too_few_assets_inconclusive(self):
        v = drift_verdict([_stats(1.0, 0.5, 3.0)] * 3, floor=0.5, min_assets=8)
        self.assertEqual(v["verdict"], "inconclusive")
        self.assertIn("insufficient", v["reason"])

    def test_drift_and_path_pass_is_exists(self):
        # 12 assets all positive ret, strong t -> sign p tiny, Z high;
        # ratio 1.0/0.5 = 2.0 >= floor 1.0
        stats = [_stats(1.0, 0.5, 3.0) for _ in range(12)]
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_exists")
        self.assertGreaterEqual(v["ratio"], 1.0)

    def test_nonpositive_pooled_ret_is_does_not_exist(self):
        stats = [_stats(-0.1, 0.5, -0.5) for _ in range(12)]
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_does_not_exist")

    def test_drift_passes_but_ratio_below_floor_is_inconclusive(self):
        # strong positive drift, but mae is huge -> ratio below floor:
        # the wall, stated precisely
        stats = [_stats(1.0, 5.0, 3.0) for _ in range(12)]
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertEqual(v["verdict"], "inconclusive")
        self.assertLess(v["ratio"], 1.0)
        self.assertIn("path", v["reason"])

    def test_breadth_fails_is_does_not_exist(self):
        # half positive half negative: sign test won't clear, pooled ret ~0+
        stats = ([_stats(1.0, 0.5, 0.2) for _ in range(6)]
                 + [_stats(-0.9, 0.5, -0.2) for _ in range(6)])
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertIn(v["verdict"], ("mechanism_does_not_exist", "inconclusive"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen.py::TestDriftVerdict -v`
Expected: FAIL with `ImportError: cannot import name 'drift_verdict'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/moonface/research/drift_screen.py
from moonface.research.oibuild_study import (binom_p_geq, stouffer,
                                             SIGN_ALPHA, STOUFFER_CRIT,
                                             MIN_ASSETS)


def drift_verdict(stats: list[dict], floor: float,
                  min_assets: int = MIN_ASSETS) -> dict:
    """Two-part pooled gate (both frozen before the run):
      1. drift exists  -> sign test p<=0.05 AND Stouffer Z>=1.645 on ret_r
      2. drift survives -> pooled mean_ret_r / pooled mean_abs_mae_r >= floor
    Tripartite verdict, mirroring oibuild_study.verdict_from."""
    m = len(stats)
    base = {"m_assets": m, "p_sign": None, "stouffer_z": None,
            "pooled_ret_r": None, "pooled_abs_mae_r": None, "ratio": None,
            "reason": ""}
    if m < min_assets:
        return {**base, "verdict": "inconclusive",
                "reason": f"insufficient evaluable assets ({m} < {min_assets})"}
    k = sum(1 for s in stats if s["mean_ret_r"] > 0)
    p_sign = binom_p_geq(k, m)
    z = stouffer([s["t"] for s in stats])
    pooled_ret = fmean([s["mean_ret_r"] for s in stats])
    pooled_mae = fmean([s["mean_abs_mae_r"] for s in stats])
    ratio = pooled_ret / pooled_mae if pooled_mae > 0 else 0.0
    base.update(k_positive=k, p_sign=p_sign, stouffer_z=z,
                pooled_ret_r=pooled_ret, pooled_abs_mae_r=pooled_mae,
                ratio=ratio)
    drift = p_sign <= SIGN_ALPHA and z >= STOUFFER_CRIT
    if drift and ratio >= floor:
        return {**base, "verdict": "mechanism_exists",
                "reason": f"breadth p={p_sign:.4g}, Z={z:.2f}, and path "
                          f"ratio={ratio:.3f} >= floor {floor:.3f}"}
    if pooled_ret <= 0.0 or not drift:
        return {**base, "verdict": "mechanism_does_not_exist",
                "reason": f"drift gate not cleared (p={p_sign:.4g}, "
                          f"Z={z:.2f}, pooled_ret_r={pooled_ret:.4f})"}
    return {**base, "verdict": "inconclusive",
            "reason": f"drift present but path ratio={ratio:.3f} < floor "
                      f"{floor:.3f} (drift unacceptable for its drawdown)"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen.py::TestDriftVerdict -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/drift_screen.py tests/test_drift_screen.py
git commit -m "feat(drift-screen): two-part pooled verdict (drift + path floor)"
```

---

## Task 4: Score one signal on one asset (events -> outcomes -> stats)

**Files:**
- Modify: `src/moonface/research/drift_screen.py`
- Test: `tests/test_drift_screen.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen.py
from moonface.research.drift_screen import score_signal_on_asset


class TestScoreSignalOnAsset(unittest.TestCase):
    def test_donchian_long_breakout_drifts_up(self):
        from moonface.backtest.edge.signals import donchian_break
        # 30 flat bars then a clean uptrend -> donchian_break(n=10) fires LONG
        flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(30)]
        up = [Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                     100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(20)]
        candles = flat + up
        stats = score_signal_on_asset(candles, donchian_break, {"n": 10},
                                      h=3, atr_period=14)
        self.assertGreater(stats["n"], 0)
        self.assertGreater(stats["mean_ret_r"], 0.0)

    def test_nonoverlap_dedupes_clustered_events(self):
        # a generator that fires every bar; with h=5 nonoverlap keeps ~1/5
        from moonface.research.drift_screen import score_signal_on_asset
        candles = [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(60)]

        def every_bar(h1, params):
            return [(i, "LONG") for i in range(20, len(h1) - 1)]

        stats = score_signal_on_asset(candles, every_bar, {}, h=5, atr_period=14)
        # ~ (len-1-20)/5 events, far fewer than the ~39 raw
        self.assertLess(stats["n"], 15)
        self.assertGreater(stats["n"], 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen.py::TestScoreSignalOnAsset -v`
Expected: FAIL with `ImportError: cannot import name 'score_signal_on_asset'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/moonface/research/drift_screen.py
from collections.abc import Callable

from moonface.research.oibuild_study import nonoverlap

Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]


def score_signal_on_asset(candles: list[Candle], generator: Generator,
                          params: dict, h: int, atr_period: int) -> dict:
    """Run one signal generator on one asset, drop serially-overlapping
    events (h-bar non-overlap), compute per-event path outcomes, return the
    per-asset path stats."""
    events = nonoverlap(generator(candles, params), h)
    outcomes: list[tuple[float, float]] = []
    for i, side in events:
        out = event_outcome(candles, i, side, h, atr_period)
        if out is not None:
            outcomes.append(out)
    return asset_path_stats(outcomes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen.py::TestScoreSignalOnAsset -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/drift_screen.py tests/test_drift_screen.py
git commit -m "feat(drift-screen): score one signal on one asset (nonoverlap + path)"
```

---

## Task 5: Screen one signal across the asset pool

**Files:**
- Modify: `src/moonface/research/drift_screen.py`
- Test: `tests/test_drift_screen.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen.py
from moonface.research.drift_screen import screen_signal


class TestScreenSignal(unittest.TestCase):
    def _up_asset(self):
        flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(30)]
        up = [Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                     100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(20)]
        return flat + up

    def test_drops_assets_below_min_events(self):
        from moonface.backtest.edge.signals import donchian_break
        pool = {f"A{j}": self._up_asset() for j in range(10)}
        # tiny asset with no events
        pool["DEAD"] = [Candle(i * H4, 100, 100, 100, 100, 1.0) for i in range(5)]
        result = screen_signal("donchian_break", donchian_break, {"n": 10},
                               pool, h=3, atr_period=14, floor=0.5,
                               min_events=1, min_assets=8)
        self.assertNotIn("DEAD", [a["sym"] for a in result["assets"]])
        self.assertIn(result["verdict"]["verdict"],
                      ("mechanism_exists", "mechanism_does_not_exist",
                       "inconclusive"))

    def test_result_carries_signal_identity(self):
        from moonface.backtest.edge.signals import donchian_break
        pool = {f"A{j}": self._up_asset() for j in range(9)}
        result = screen_signal("donchian_break", donchian_break, {"n": 10},
                               pool, h=3, atr_period=14, floor=0.5,
                               min_events=1, min_assets=8)
        self.assertEqual(result["signal"], "donchian_break")
        self.assertEqual(result["params"], {"n": 10})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen.py::TestScreenSignal -v`
Expected: FAIL with `ImportError: cannot import name 'screen_signal'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/moonface/research/drift_screen.py
from moonface.research.oibuild_study import MIN_EVENTS_PER_ASSET


def screen_signal(name: str, generator: Generator, params: dict,
                  pool: dict[str, list[Candle]], h: int, atr_period: int,
                  floor: float, min_events: int = MIN_EVENTS_PER_ASSET,
                  min_assets: int = MIN_ASSETS) -> dict:
    """Screen one signal across the fresh-asset pool. Each asset with at least
    min_events non-overlapping tradeable events is one unit of evidence; the
    pooled two-part verdict is computed over those assets."""
    per_asset: list[dict] = []
    for sym in sorted(pool):
        stats = score_signal_on_asset(pool[sym], generator, params, h, atr_period)
        if stats["n"] >= min_events:
            per_asset.append({"sym": sym, **stats})
    verdict = drift_verdict(per_asset, floor=floor, min_assets=min_assets)
    return {"signal": name, "params": params, "h": h,
            "assets": per_asset, "verdict": verdict}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen.py::TestScreenSignal -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/drift_screen.py tests/test_drift_screen.py
git commit -m "feat(drift-screen): pool screen for one signal -> verdict"
```

---

## Task 6: Phase A — calibrate the floor from existing result files

**Files:**
- Create: `tools/drift_screen.py` (with `phase-a` subcommand only for now)
- Create: `tests/test_drift_screen_cli.py`

This task reads `experiments/edge/20260609T171708Z/leaderboard.json` and
`experiments/positioning_exits/20260610T065146Z/positioning_exit_probe.json`,
converts each row's drift and drawdown into a comparable `ret_r / |mae_r|`-style
ratio, and emits the descriptive report plus the calibrated floor. The floor is
set to the smallest ratio that the **known-dead** families fail to clear (so the
screen, by construction, rejects what is already known dead).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drift_screen_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from tools.drift_screen import compute_floor_from_rows


class TestPhaseAFloor(unittest.TestCase):
    def test_floor_is_max_ratio_among_dead_rows(self):
        # each row: forward drift R and the adverse drawdown R it lived through.
        # All rows are known-dead (invalid). Floor must exceed every dead ratio
        # so the screen rejects them, i.e. floor = max(dead ratios) (exclusive
        # bar applied at >= in the gate, so we record max + a tiny epsilon).
        dead = [
            {"drift_r": 1.63, "dd_r": 114.0},   # funding_fade horizon_hold
            {"drift_r": 1.13, "dd_r": 32.0},    # funding_fade fixed_bracket
            {"drift_r": 0.60, "dd_r": 60.0},
        ]
        floor = compute_floor_from_rows(dead)
        # ratios: 0.0143, 0.0353, 0.0100 -> max 0.0353
        self.assertAlmostEqual(floor, 0.0353, places=3)

    def test_empty_rows_floor_is_one(self):
        # with no evidence, fall back to the conservative a-priori bar 1.0
        self.assertEqual(compute_floor_from_rows([]), 1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestPhaseAFloor -v`
Expected: FAIL with `ModuleNotFoundError` / `cannot import name 'compute_floor_from_rows'`.

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python
# tools/drift_screen.py
"""Drawdown-aware drift screen CLI.

phase-a : calibrate the path-ratio floor from existing edge/positioning
          result files and write the descriptive gap report.
register: freeze the design (horizon, floor, universe, exclude set).
run     : load 4h candles for the frozen universe, screen every registered
          signal under the path-aware gate, write the leaderboard.

Mechanism science only: a single fixed horizon, no exits/stops/TPs/grids.
Design frozen in experiments/drift_screen/PREREGISTRATION.md."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def compute_floor_from_rows(rows: list[dict]) -> float:
    """Floor = the largest drift/drawdown ratio observed among known-dead
    rows, so the gate (ratio >= floor) rejects everything already known dead.
    Falls back to the conservative a-priori bar 1.0 when there is no evidence."""
    if not rows:
        return 1.0
    ratios = [r["drift_r"] / r["dd_r"] for r in rows if r["dd_r"] > 0]
    return max(ratios) if ratios else 1.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestPhaseAFloor -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/drift_screen.py tests/test_drift_screen_cli.py
git commit -m "feat(drift-screen): phase-a floor calibration from known-dead rows"
```

---

## Task 7: Phase A — wire the report and run it

**Files:**
- Modify: `tools/drift_screen.py`
- Test: `tests/test_drift_screen_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen_cli.py
from tools.drift_screen import (load_positioning_rows, load_edge_rows,
                                 cmd_phase_a)


class TestPhaseAReport(unittest.TestCase):
    def test_positioning_rows_extract_drift_and_dd(self):
        payload = {"rows": [
            {"oos_expectancy_r": 1.63, "research_max_dd_r": -114.0},
            {"oos_expectancy_r": -0.2, "research_max_dd_r": -50.0},
        ]}
        rows = load_positioning_rows(payload)
        # only positive-drift rows are dead-but-drifting evidence
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["drift_r"], 1.63)
        self.assertAlmostEqual(rows[0]["dd_r"], 114.0)

    def test_edge_rows_extract_horizon_drift(self):
        payload = {"rows": [
            {"hzn_oos_exp": 1.27, "brkt_net_r": -9.6, "brkt_exp": -0.09},
            {"hzn_oos_exp": -0.1, "brkt_net_r": -1.0, "brkt_exp": -0.01},
        ]}
        rows = load_edge_rows(payload)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["drift_r"], 1.27)

    def test_cmd_phase_a_writes_report_and_floor(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            pos = out / "pos.json"
            edge = out / "edge.json"
            pos.write_text(json.dumps({"rows": [
                {"oos_expectancy_r": 1.63, "research_max_dd_r": -114.0}]}))
            edge.write_text(json.dumps({"rows": [
                {"hzn_oos_exp": 1.27, "brkt_net_r": -9.6, "brkt_exp": -0.09}]}))
            floor = cmd_phase_a(out, positioning=pos, edge=edge)
            self.assertTrue((out / "phaseA_gap.md").exists())
            self.assertGreater(floor, 0.0)
            report = (out / "phaseA_gap.md").read_text()
            self.assertIn("calibrated floor", report.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestPhaseAReport -v`
Expected: FAIL with `cannot import name 'load_positioning_rows'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to tools/drift_screen.py


def load_positioning_rows(payload: dict) -> list[dict]:
    """Positioning exit probe rows -> dead-but-drifting evidence: OOS
    expectancy (R/trade) as drift, |research max drawdown R| as the path cost.
    Only positive-drift rows are evidence of harvestable-looking drift."""
    out: list[dict] = []
    for r in payload.get("rows", []):
        drift = float(r["oos_expectancy_r"])
        if drift > 0:
            out.append({"drift_r": drift,
                        "dd_r": abs(float(r["research_max_dd_r"]))})
    return out


def load_edge_rows(payload: dict) -> list[dict]:
    """Edge leaderboard rows -> evidence: horizon OOS expectancy as drift,
    |bracket expectancy| floored at a small positive as path cost proxy. Only
    positive-drift rows count."""
    out: list[dict] = []
    for r in payload.get("rows", []):
        drift = float(r.get("hzn_oos_exp", 0.0))
        if drift > 0:
            dd = abs(float(r.get("brkt_exp", 0.0))) or 1e-6
            out.append({"drift_r": drift, "dd_r": dd})
    return out


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def cmd_phase_a(out_dir: Path, positioning: Path, edge: Path) -> float:
    pos_rows = load_positioning_rows(_read_json(positioning))
    edge_rows = load_edge_rows(_read_json(edge))
    dead = pos_rows + edge_rows
    floor = compute_floor_from_rows(dead)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Drift screen — Phase A gap characterization", "",
             f"- known-dead drifting rows: {len(dead)}",
             f"- **calibrated floor (ret_r/|mae_r|): {floor:.4f}**",
             "  (largest drift/drawdown ratio among known-dead families;",
             "   the gate ratio >= floor therefore rejects all of them)", "",
             "## Known-dead drift-vs-drawdown rows", "",
             "| drift_r | dd_r | ratio |", "|---|---|---|"]
    for r in sorted(dead, key=lambda x: x["drift_r"] / x["dd_r"], reverse=True):
        lines.append(f"| {r['drift_r']:.4f} | {r['dd_r']:.4f} "
                     f"| {r['drift_r'] / r['dd_r']:.4f} |")
    (out_dir / "phaseA_gap.md").write_text("\n".join(lines) + "\n")
    return floor


def _add_phase_a(sub) -> None:
    p = sub.add_parser("phase-a", help="calibrate floor from existing results")
    p.add_argument("--positioning", type=Path, required=True)
    p.add_argument("--edge", type=Path, required=True)
    p.add_argument("--out", type=Path,
                   default=Path("experiments/drift_screen"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestPhaseAReport -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run Phase A for real and commit the report**

```bash
python tools/drift_screen.py phase-a \
  --positioning experiments/positioning_exits/20260610T065146Z/positioning_exit_probe.json \
  --edge experiments/edge/20260609T171708Z/leaderboard.json \
  --out experiments/drift_screen
```
Note: if the real JSON uses different key names than the test fixtures
(`rows`, `oos_expectancy_r`, `research_max_dd_r`, `hzn_oos_exp`, `brkt_exp`),
adjust `load_positioning_rows` / `load_edge_rows` to the actual schema —
inspect with `python -c "import json;print(list(json.load(open(PATH))['rows'][0]))"`
first — and re-run. Then:

```bash
git add -f tools/drift_screen.py tests/test_drift_screen_cli.py experiments/drift_screen/phaseA_gap.md
git commit -m "feat(drift-screen): phase-a report + calibrated floor from real results"
```

---

## Task 8: CLI `register` — freeze the design

**Files:**
- Modify: `tools/drift_screen.py`
- Test: `tests/test_drift_screen_cli.py`

The frozen universe is the 16 oibuild confirmation assets (excluding the
BTC/ETH/SOL discovery set), and the registered signals are the existing-registry
generators from the H4 edge leaderboard plus the funding/positioning entries.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen_cli.py
from tools.drift_screen import cmd_register, DESIGN


class TestRegister(unittest.TestCase):
    def test_register_freezes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            cmd_register(out, floor=0.05)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["floor"], 0.05)
            self.assertEqual(reg["h"], DESIGN["h"])
            self.assertNotIn("BTCUSDT", reg["universe"])
            self.assertTrue(len(reg["signals"]) >= 3)
            with self.assertRaises(SystemExit):
                cmd_register(out, floor=0.05)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestRegister -v`
Expected: FAIL with `cannot import name 'cmd_register'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to tools/drift_screen.py
import datetime as dt

# The 16 fresh confirmation assets from the oibuild study (discovery set
# BTC/ETH/SOL excluded). 4h OHLC for these lives in .backtest_cache.
UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT"]

DISCOVERY = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Existing-registry signals to re-score. Resolved to generators at run time
# (kept as names here so registration.json stays pure JSON).
SIGNALS = [
    {"name": "donchian_break", "params": {"n": 100}},
    {"name": "donchian_break", "params": {"n": 55}},
    {"name": "atr_channel_break", "params": {"k": 1.5, "atr_period": 14}},
    {"name": "atr_channel_break", "params": {"k": 2.0, "atr_period": 14}},
    {"name": "ma_cross", "params": {"fast": 50, "slow": 200}},
    {"name": "roc_sign", "params": {"period": 24}},
    {"name": "price_vs_ma", "params": {"period": 100}},
]

DESIGN = {
    "timeframe": "4h", "h": 24, "atr_period": 14,
    "min_events": 10, "min_assets": 8,
    "universe": UNIVERSE, "discovery": DISCOVERY, "signals": SIGNALS,
}


def cmd_register(out_dir: Path, floor: float) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    reg = dict(DESIGN)
    reg["floor"] = floor
    reg["registered_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} (floor={floor}, {len(SIGNALS)} signals frozen)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestRegister -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add tools/drift_screen.py tests/test_drift_screen_cli.py
git commit -m "feat(drift-screen): register subcommand freezes universe/signals/floor"
```

---

## Task 9: CLI `run` — load candles, screen all signals, write leaderboard

**Files:**
- Modify: `tools/drift_screen.py`
- Test: `tests/test_drift_screen_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen_cli.py
from moonface.models import Candle
from tools.drift_screen import cmd_run, resolve_signal

H4 = 4 * 3_600_000


class TestRun(unittest.TestCase):
    def test_resolve_signal_maps_name_to_generator(self):
        gen = resolve_signal("donchian_break")
        from moonface.backtest.edge.signals import donchian_break
        self.assertIs(gen, donchian_break)

    def test_run_writes_leaderboard_from_loader(self):
        def _asset():
            flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(40)]
            up = [Candle((40 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                         100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(40)]
            return flat + up

        reg = {"timeframe": "4h", "h": 3, "atr_period": 14,
               "min_events": 1, "min_assets": 8, "floor": 0.05,
               "universe": [f"A{j}" for j in range(9)],
               "signals": [{"name": "donchian_break", "params": {"n": 10}}]}

        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "registration.json").write_text(json.dumps(reg))
            cmd_run(out, loader=lambda sym, tf: _asset())
            board = json.loads((out / "leaderboard.json").read_text())
            self.assertEqual(len(board), 1)
            self.assertEqual(board[0]["signal"], "donchian_break")
            self.assertIn("verdict", board[0])
            self.assertTrue((out / "leaderboard.md").exists())

    def test_run_skips_missing_assets(self):
        reg = {"timeframe": "4h", "h": 3, "atr_period": 14,
               "min_events": 1, "min_assets": 8, "floor": 0.05,
               "universe": ["PRESENT", "MISSING"],
               "signals": [{"name": "donchian_break", "params": {"n": 10}}]}
        present = [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(50)]

        def loader(sym, tf):
            return present if sym == "PRESENT" else None

        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "registration.json").write_text(json.dumps(reg))
            cmd_run(out, loader=loader)  # must not raise on MISSING
            board = json.loads((out / "leaderboard.json").read_text())
            self.assertEqual(len(board), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestRun -v`
Expected: FAIL with `cannot import name 'cmd_run'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to tools/drift_screen.py
from collections.abc import Callable

from moonface.models import Candle
from moonface.backtest.edge.signals import (atr_channel_break, donchian_break,
                                             ma_cross, price_vs_ma, roc_sign)
from moonface.research.drift_screen import screen_signal

_REGISTRY = {
    "donchian_break": donchian_break, "atr_channel_break": atr_channel_break,
    "ma_cross": ma_cross, "price_vs_ma": price_vs_ma, "roc_sign": roc_sign,
}

Loader = Callable[[str, str], "list[Candle] | None"]


def resolve_signal(name: str):
    return _REGISTRY[name]


def _default_loader(cache_dir: str = ".backtest_cache") -> Loader:
    from moonface.backtest.data import OhlcvCache
    cache = OhlcvCache(cache_dir)
    return lambda sym, tf: cache.load(sym, tf)


def cmd_run(out_dir: Path, loader: Loader | None = None) -> None:
    reg = json.loads((out_dir / "registration.json").read_text())
    if loader is None:
        loader = _default_loader()
    tf = reg["timeframe"]
    pool: dict[str, list[Candle]] = {}
    for sym in reg["universe"]:
        candles = loader(sym, tf)
        if candles:
            pool[sym] = candles
    results = []
    for sig in reg["signals"]:
        results.append(screen_signal(
            sig["name"], resolve_signal(sig["name"]), sig["params"], pool,
            h=reg["h"], atr_period=reg["atr_period"], floor=reg["floor"],
            min_events=reg["min_events"], min_assets=reg["min_assets"]))
    results.sort(key=lambda r: (r["verdict"]["ratio"] or -1.0), reverse=True)
    (out_dir / "leaderboard.json").write_text(json.dumps(results, indent=2))
    (out_dir / "leaderboard.md").write_text(_render_md(results))
    print(f"screened {len(results)} signals over {len(pool)} assets "
          f"-> {out_dir / 'leaderboard.md'}")


def _render_md(results: list[dict]) -> str:
    lines = ["# Drift screen — leaderboard", "",
             "| signal | params | m | p_sign | Z | pooled_ret_r "
             "| pooled_|mae|_r | ratio | verdict |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        v = r["verdict"]
        lines.append(
            f"| {r['signal']} | {r['params']} | {v['m_assets']} "
            f"| {_f(v['p_sign'])} | {_f(v['stouffer_z'])} "
            f"| {_f(v['pooled_ret_r'])} | {_f(v['pooled_abs_mae_r'])} "
            f"| {_f(v['ratio'])} | {v['verdict']} |")
    return "\n".join(lines) + "\n"


def _f(x) -> str:
    return "" if x is None else f"{x:.4f}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestRun -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/drift_screen.py tests/test_drift_screen_cli.py
git commit -m "feat(drift-screen): run subcommand screens all signals -> leaderboard"
```

---

## Task 10: Wire the argparse entrypoint

**Files:**
- Modify: `tools/drift_screen.py`
- Test: `tests/test_drift_screen_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_drift_screen_cli.py
import subprocess


class TestEntrypoint(unittest.TestCase):
    def test_help_lists_subcommands(self):
        out = subprocess.run(
            [sys.executable, "tools/drift_screen.py", "--help"],
            capture_output=True, text=True)
        self.assertIn("phase-a", out.stdout)
        self.assertIn("register", out.stdout)
        self.assertIn("run", out.stdout)


import sys  # noqa: E402  (kept with the test that uses it)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestEntrypoint -v`
Expected: FAIL (no subcommands wired; `--help` lacks them or script errors).

- [ ] **Step 3: Write minimal implementation**

```python
# append to tools/drift_screen.py


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="drawdown-aware drift screen")
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_phase_a(sub)

    pr = sub.add_parser("register", help="freeze design (floor from phase-a)")
    pr.add_argument("--floor", type=float, required=True)
    pr.add_argument("--out", type=Path, default=Path("experiments/drift_screen"))

    rn = sub.add_parser("run", help="screen all signals -> leaderboard")
    rn.add_argument("--out", type=Path, default=Path("experiments/drift_screen"))

    args = parser.parse_args(argv)
    if args.cmd == "phase-a":
        floor = cmd_phase_a(args.out, positioning=args.positioning, edge=args.edge)
        print(f"calibrated floor: {floor:.4f}")
    elif args.cmd == "register":
        cmd_register(args.out, floor=args.floor)
    elif args.cmd == "run":
        cmd_run(args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drift_screen_cli.py::TestEntrypoint -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add tools/drift_screen.py tests/test_drift_screen_cli.py
git commit -m "feat(drift-screen): argparse entrypoint (phase-a|register|run)"
```

---

## Task 11: Pre-registration, real run, and verdict capture

**Files:**
- Create: `experiments/drift_screen/PREREGISTRATION.md`
- Create (by run): `experiments/drift_screen/registration.json`, `leaderboard.{md,json}`

- [ ] **Step 1: Write the pre-registration document**

Create `experiments/drift_screen/PREREGISTRATION.md` stating verbatim: the
frozen horizon (`h=24` 4h bars), atr_period 14, the calibrated floor (the
number Phase A wrote into `phaseA_gap.md`), the 16-asset universe, the excluded
discovery set (BTC/ETH/SOL), the 7 registered signals, `min_events=10`,
`min_assets=8`, and the two-part gate + tripartite verdict rule. Include the
sentence: "No exits, stops, take-profits, or grids of any kind are fit; a single
fixed horizon is scored. The floor was calibrated against known-dead families in
Phase A and is frozen here before any real run."

- [ ] **Step 2: Freeze the registration**

```bash
FLOOR=$(python -c "import re,pathlib;print(re.search(r'calibrated floor.*?:\s*([0-9.]+)', pathlib.Path('experiments/drift_screen/phaseA_gap.md').read_text()).group(1))")
echo "floor = $FLOOR"
python tools/drift_screen.py register --floor "$FLOOR" --out experiments/drift_screen
```
Expected: prints `registered: experiments/drift_screen/registration.json (...)`.

- [ ] **Step 3: Run the screen on real cached candles**

```bash
python tools/drift_screen.py run --out experiments/drift_screen
```
Expected: prints `screened 7 signals over N assets -> .../leaderboard.md`,
where N is the number of the 16 universe symbols that have a `*_4h.csv` in
`.backtest_cache`. If N < min_assets (8) for most signals, the verdicts will be
`inconclusive` for insufficient assets — note that in the commit message and
verify which `*USDT_4h.csv` files are actually present:
`ls .backtest_cache/*USDT_4h.csv | wc -l`.

- [ ] **Step 4: Verify the full suite is green and lint is clean**

```bash
python -m pytest tests/test_drift_screen.py tests/test_drift_screen_cli.py -v
ruff check src/moonface/research/drift_screen.py tools/drift_screen.py
```
Expected: all tests PASS; `ruff` reports no issues.

- [ ] **Step 5: Commit the frozen design, results, and pre-registration**

```bash
git add -f experiments/drift_screen/PREREGISTRATION.md \
            experiments/drift_screen/registration.json \
            experiments/drift_screen/leaderboard.json \
            experiments/drift_screen/leaderboard.md
git commit -m "feat(drift-screen): pre-registration + real-data verdict over fresh assets"
```

---

## Task 12: Full-suite green + memory note

**Files:**
- Modify: memory (`MEMORY.md` + a new memory file)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: all tests PASS (the prior ~304 plus the new drift-screen tests).

- [ ] **Step 2: Run ruff across the repo touchpoints**

Run: `ruff check src tools tests`
Expected: no issues.

- [ ] **Step 3: Record the outcome in memory**

Write `…/memory/drift-screen-results.md` (type: project) capturing the verdict
per signal from `leaderboard.md`, the calibrated floor, and whether the
drawdown wall was confirmed structural (all `inconclusive`/`does_not_exist`) or
a survivor emerged (`mechanism_exists`). Add a one-line pointer to `MEMORY.md`.
Link `[[oibuild-mechanism-verdict]]` and `[[positioning-exit-probe-results]]`.

- [ ] **Step 4: Commit the memory note**

```bash
git add -f .claude/projects/*/memory/MEMORY.md .claude/projects/*/memory/drift-screen-results.md 2>/dev/null || true
git commit -m "docs(memory): drift-screen results" || echo "memory is outside repo; skip"
```
Note: memory lives under `~/.claude`, outside this repo — if `git add` finds
nothing, the memory write in Step 3 still stands; just skip the commit.

---

## Self-Review Notes

- **Spec coverage:** Phase A (Tasks 6–7), path-aware outcome in R (Task 1), two-part
  gate + tripartite verdict (Task 3), exit-free single horizon (no exit params anywhere),
  fresh-asset universe excluding discovery set (Task 8), reuse of oibuild stats (Tasks 2–5),
  pre-registration before run (Task 11), TDD throughout, conservative-bias accepted (4h-low
  MAE, noted in spec). All covered.
- **Floor discretion:** calibrated from known-dead rows (Task 6), pre-registered before the
  real run (Task 11) — the one outcome-coupled knob is neutralized exactly as the spec's
  discretion principle requires.
- **Type consistency:** `event_outcome -> (ret_r, mae_r)`; `asset_path_stats` keys
  `n/mean_ret_r/mean_abs_mae_r/t`; `drift_verdict` keys include `ratio`; `screen_signal`
  returns `{signal, params, h, assets, verdict}`; CLI `resolve_signal`/`cmd_run` consume
  those exact shapes. Consistent across tasks.
- **Schema risk flagged:** Task 7 Step 5 explicitly says to verify the real edge/positioning
  JSON key names before the Phase A run, since the report-rendering keys are assumptions
  from the `.md` columns, not confirmed against the `.json`.
```
