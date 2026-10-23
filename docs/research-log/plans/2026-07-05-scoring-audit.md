# v2 Scoring Component & Weight Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the read-only, two-stage audit that answers, per book and per direction, whether each of the 12 confluence modules contributes outcome-ordering signal and whether any nonnegative reweighting achieves out-of-sample ordering.

**Architecture:** A new `audit.py` module reuses the calibration harness's panel machinery unchanged (bit-identical panel semantics), adding LOO marginal contribution, per-module conditional ordering, a chronological-split fitted upper bound (pure-stdlib NNLS + logistic), and verdict logic. A new CLI mirrors `tools/engine_calibration.py`. Stage 2 adds `deriv_history.py`, reconstructing per-bar `DerivSnapshot`s from the existing cached funding and Binance Vision metrics loaders.

**Tech Stack:** Python 3.12 (repo `.venv`), stdlib only in `src/` (no numpy), pytest with plain test functions, deterministic `random.Random(seed)` bootstraps.

**Spec:** `docs/research-log/specs/2026-07-05-scoring-audit-design.md`

## Global Constraints

- **Read-only posture:** never modify engine constants, `promotion/engine.json`, `journal/`, or any registration doc. The v2.1 clock (hash `4e35561fe6b7d639712e10f8b87d78b5cf0a6d629d9ccc2cac8d605909305a6a`) is untouched.
- **stdlib only** in `src/moonface/` — no numpy/scipy (numpy is an optional dev extra for an unrelated lane).
- **Inference constants identical to calibration** for comparability: block 168 bars, 1000 draws, seed 20260704, panel floor 200.
- **Tests hermetic:** no network, no `.backtest_cache` reads; inject synthetic data. Run tests as `.venv/bin/python -m pytest <file> -q`.
- **Test style:** plain pytest functions (see `tests/test_engine_calibration_pass.py`), synthetic candles via a seeded random walk.
- **Registered calibration CLI (`tools/engine_calibration.py`) behavior must not change.**
- **Git:** never chain `git add && git commit` — stage, then verify `git diff --cached --stat`, then commit. No AI-attribution trailers. `docs/` is globally gitignored but specs/plans are tracked by repo convention — use `git add -f` for files under `docs/`.
- **One-run rule:** registered runs (Tasks 9, 11) execute once; re-run only on mechanical failure, never to revisit a completed result.

---

### Task 1: Deriv seam in `scoring_pass` (behavior-preserving)

**Files:**
- Modify: `src/moonface/signal/engine/calibration.py:94-107` (`scoring_pass`)
- Test: `tests/test_engine_calibration_pass.py` (append)

**Interfaces:**
- Produces: `scoring_pass(cfg: EngineConfig, candles: list[Candle], warmup: int, deriv_by_index: dict[int, DerivSnapshot] | None = None) -> list[BarRow]`. Later tasks (6, 8) pass `deriv_by_index`; default `None` must reproduce current rows exactly.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_engine_calibration_pass.py`:

```python
def test_scoring_pass_deriv_default_matches_empty_map():
    # Regression guard: the new deriv_by_index seam with None (default) and {}
    # must be byte-identical to the pre-seam behavior.
    candles = _walk_series(420)
    cfg = _cfg()
    base = scoring_pass(cfg, candles, warmup=380)
    assert scoring_pass(cfg, candles, warmup=380, deriv_by_index=None) == base
    assert scoring_pass(cfg, candles, warmup=380, deriv_by_index={}) == base


def test_scoring_pass_deriv_snapshot_reaches_funding_module():
    from moonface.signal.engine.deriv import DerivSnapshot
    candles = _walk_series(420)
    cfg = _cfg()
    base = scoring_pass(cfg, candles, warmup=380)
    # first bar where the trend book has a direction: neutral funding (pct=50)
    # scores 5 points either way, so m5_funding must become nonzero there.
    target = next(r for r in base if r.trend.direction != 0)
    assert base[target.index - 380].module_points["m5_funding"] == 0
    rows = scoring_pass(cfg, candles, warmup=380, deriv_by_index={
        target.index: DerivSnapshot(funding_pct=50.0)})
    assert abs(rows[target.index - 380].module_points["m5_funding"]) == 5
    # every other bar is untouched
    for old, new in zip(base, rows):
        if old.index != target.index:
            assert old == new
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py -q`
Expected: FAIL — `TypeError: scoring_pass() got an unexpected keyword argument 'deriv_by_index'`

- [ ] **Step 3: Implement the seam** — in `src/moonface/signal/engine/calibration.py`, change `scoring_pass` (only these lines):

```python
def scoring_pass(cfg: EngineConfig, candles: list[Candle], warmup: int,
                 deriv_by_index: dict[int, "DerivSnapshot"] | None = None,
                 ) -> list[BarRow]:
    """Mirror the frozen evaluate_engine scoring sequence over a rolling window.

    deriv_by_index (audit Stage 2): per-bar historical DerivSnapshots keyed by
    candle index. Default None preserves the registered deriv=None behavior
    exactly."""
    window = cfg.lookback_bars
    rows: list[BarRow] = []
    for j in range(warmup, len(candles)):
        lo = max(0, j + 1 - window)
        sub = candles[lo:j + 1]
        views = trend_book.build_views(sub)
        regime = classify_regime(views.h4, cfg)
        macro = classify_macro(views.w1, regime.vol_state, cfg)
        deriv = deriv_by_index.get(j) if deriv_by_index is not None else None
        trend_scores = trend_book.score(views, macro, deriv, cfg)
        revert_scores = revert_book.score(views, macro, deriv, cfg)
```

(the rest of the function body is unchanged), and add the import at the top with the other engine imports:

```python
from moonface.signal.engine.deriv import DerivSnapshot
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py -q`
Expected: PASS (all tests in the file, including the pre-existing parity tests)

- [ ] **Step 5: Run the calibration suite to prove no regression**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py tests/test_engine_calibration_sim.py tests/test_engine_calibration_stats.py tests/test_engine_calibration_report.py tests/test_engine_calibration_cli.py -q`
Expected: PASS, zero failures

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/calibration.py tests/test_engine_calibration_pass.py
git diff --cached --stat
git commit -m "feat(engine): deriv_by_index seam in scoring_pass (default preserves registered behavior)"
```

---

### Task 2: `audit.py` foundation — generalized block bootstrap + baseline ordering

**Files:**
- Create: `src/moonface/signal/engine/audit.py`
- Test: `tests/test_engine_audit_stats.py`

**Interfaces:**
- Consumes: `calibration.spearman`, `calibration.HypoTrade`, constants.
- Produces:
  - `block_ci(items: list, key_fn, stat_fn, block_bars=168, draws=1000, seed=20260704) -> tuple[float, float] | None` — 95% CI of `stat_fn(sample)` via moving-block bootstrap keyed on `key_fn(item) // block_bars`.
  - `baseline_ordering(panel: list[HypoTrade]) -> dict` — per split (`pooled`/`LONG`/`SHORT`): `{n, spearman_rho, rho_ci_95, status}`.
  - `_split_trades(panel, split)`, `_rho_stat(trades)` (reused by later tasks).

- [ ] **Step 1: Write the failing tests** — create `tests/test_engine_audit_stats.py`:

```python
"""Foundation stats of the scoring audit (spec 2026-07-05, §5.1).

block_ci must reproduce calibration.block_bootstrap_rho_ci when given the
same stat, so audit CIs stay comparable with the 2026-07 baseline."""
import random

from moonface.signal.engine.audit import (baseline_ordering, block_ci,
                                          _rho_stat, _split_trades)
from moonface.signal.engine.calibration import (HypoTrade,
                                                block_bootstrap_rho_ci)

H = 3_600_000


def _mk_trade(i, direction, score, net_r):
    return HypoTrade(entry_index=i, exit_index=i + 3, entry_ts_ms=i * H,
                     exit_ts_ms=(i + 3) * H, book="trend",
                     direction=direction, score=score, breadth=3,
                     policy="ALLOW", macro_effective="NEUTRAL",
                     vol_state="normal", net_r=net_r, bars_held=3,
                     exit_reason="stop")


def _panel(n=1200, seed=1, informative=True):
    rng = random.Random(seed)
    out = []
    for k in range(n):
        score = rng.choice((20, 40, 60, 80))
        noise = rng.gauss(0.0, 0.5)
        net_r = (0.02 * score + noise) if informative else noise
        direction = 1 if k % 3 else -1
        out.append(_mk_trade(k * 35, direction, score, round(net_r, 4)))
    return out


def test_block_ci_matches_calibration_bootstrap_for_rho():
    panel = _panel()
    ours = block_ci(panel, lambda t: t.entry_index, _rho_stat)
    theirs = block_bootstrap_rho_ci(panel)
    assert ours is not None and theirs is not None
    assert abs(ours[0] - theirs[0]) < 1e-12
    assert abs(ours[1] - theirs[1]) < 1e-12


def test_block_ci_single_block_returns_none():
    panel = [_mk_trade(i, 1, 60, 0.1) for i in range(5)]  # all in block 0
    assert block_ci(panel, lambda t: t.entry_index, _rho_stat) is None


def test_split_trades_directions():
    panel = _panel(n=30)
    longs = _split_trades(panel, "LONG")
    shorts = _split_trades(panel, "SHORT")
    assert all(t.direction == 1 for t in longs)
    assert all(t.direction == -1 for t in shorts)
    assert len(longs) + len(shorts) == len(_split_trades(panel, "pooled"))


def test_baseline_ordering_shape_and_power_floor():
    report = baseline_ordering(_panel())
    assert set(report) == {"pooled", "LONG", "SHORT"}
    pooled = report["pooled"]
    assert pooled["n"] == 1200
    assert pooled["status"] == "ok"
    assert pooled["spearman_rho"] > 0.3          # informative panel
    assert pooled["rho_ci_95"][0] > 0
    tiny = baseline_ordering(_panel(n=150))
    assert tiny["pooled"]["status"] == "UNDERPOWERED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_stats.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.signal.engine.audit'`

- [ ] **Step 3: Create `src/moonface/signal/engine/audit.py`:**

```python
"""Read-only scoring component & weight audit for the frozen v2 core.

Spec: docs/research-log/specs/2026-07-05-scoring-audit-design.md.
Pre-registration: experiments/engine/SCORING_AUDIT_2026-07.md.

Imports the calibration panel machinery UNCHANGED so panel semantics stay
bit-identical to the 2026-07 calibration baseline. DIAGNOSTIC ONLY — never
gates, never mutates state, never recommends a constant change; any future
v2.2 is a separate human decision with a new registration.
"""
from __future__ import annotations

import math
import random

from moonface.signal.engine.calibration import (BLOCK_BARS, BOOTSTRAP_DRAWS,
                                                BOOTSTRAP_SEED, PANEL_FLOOR,
                                                _REVERT_MODULES,
                                                _TREND_MODULES, BarRow,
                                                HypoTrade, spearman)

BOOK_MODULES: dict[str, tuple[str, ...]] = {
    "trend": _TREND_MODULES,
    "mean_revert": _REVERT_MODULES,
}
_SPLITS = ("pooled", "LONG", "SHORT")

AUDIT_LABEL = ("scoring audit — read-only, no edge claim, "
               "no constant recommendation")


def block_ci(items: list, key_fn, stat_fn, block_bars: int = BLOCK_BARS,
             draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED,
             ) -> tuple[float, float] | None:
    """95% CI of stat_fn(resample) via a moving-block bootstrap keyed on
    key_fn(item) // block_bars. Generalizes calibration.block_bootstrap_rho_ci
    (same blocks, draws, seed, and percentile rule) to arbitrary statistics."""
    blocks: dict[int, list] = {}
    for it in items:
        blocks.setdefault(key_fn(it) // block_bars, []).append(it)
    keys = sorted(blocks)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(draws):
        sample: list = []
        for _ in range(len(keys)):
            sample.extend(blocks[keys[rng.randrange(len(keys))]])
        s = stat_fn(sample)
        if s is not None:
            stats.append(s)
    if len(stats) < draws // 2:
        return None
    stats.sort()
    return (stats[int(0.025 * (len(stats) - 1))],
            stats[int(0.975 * (len(stats) - 1))])


def _split_trades(panel: list[HypoTrade], split: str) -> list[HypoTrade]:
    if split == "pooled":
        return list(panel)
    want = 1 if split == "LONG" else -1
    return [t for t in panel if t.direction == want]


def _rho_stat(trades: list[HypoTrade]) -> float | None:
    return spearman([float(t.score) for t in trades],
                    [t.net_r for t in trades])


def _ci_out(ci: tuple[float, float] | None) -> list[float] | None:
    return [round(ci[0], 4), round(ci[1], 4)] if ci is not None else None


def baseline_ordering(panel: list[HypoTrade]) -> dict:
    """Spearman(score, net R) with CI, per split — including the per-direction
    ordering the 2026-07 report lacked (it had per-direction mean R only)."""
    out: dict[str, dict] = {}
    for split in _SPLITS:
        trades = _split_trades(panel, split)
        rho = _rho_stat(trades)
        ci = block_ci(trades, lambda t: t.entry_index, _rho_stat)
        out[split] = {
            "n": len(trades),
            "spearman_rho": round(rho, 4) if rho is not None else None,
            "rho_ci_95": _ci_out(ci),
            "status": ("UNDERPOWERED" if len(trades) < PANEL_FLOOR else "ok"),
        }
    return out
```

(`math`, `BarRow`, and `BOOK_MODULES` are unused until Tasks 3–5 — that is fine; they land now so the module header is complete.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_stats.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/audit.py tests/test_engine_audit_stats.py
git diff --cached --stat
git commit -m "feat(audit): generalized block bootstrap + per-direction baseline ordering"
```

---

### Task 3: Leave-one-out marginal contribution

**Files:**
- Create: `tests/helpers_audit.py` (shared synthetic fixtures — repo precedent: `tests/helpers_consolidated.py`)
- Modify: `src/moonface/signal/engine/audit.py` (append)
- Test: `tests/test_engine_audit_loo.py`

**Interfaces:**
- Consumes: `block_ci`, `BOOK_MODULES`, `spearman` from Task 2; `BarRow.module_points` (signed points, all 12 modules).
- Produces:
  - `loo_book_score(row: BarRow, book: str, drop: str) -> tuple[int, int]` — (direction, score) of the book sum without `drop`.
  - `loo_analysis(panel: list[HypoTrade], rows_by_index: dict[int, BarRow], book: str) -> dict` — per module: `{n_direction_changed, splits: {pooled/LONG/SHORT: {n_kept, delta_rho, delta_ci_95, class}}}` with class ∈ CONTRIBUTES / DEAD / HARMFUL / UNDERPOWERED (per-direction LOO classes are part of the spec §7 evidence table).
  - Test helpers in `tests/helpers_audit.py`: `_walk_series(n, seed=7, start=100.0)`, `_mk_row(i, pts)`, `_mk_trade(i, score, net_r, direction=1)`, `_fixture(n=1200, seed=2)` — imported by Tasks 4–6 and 8 tests.

- [ ] **Step 1: Create `tests/helpers_audit.py`:**

```python
"""Shared synthetic fixtures for the scoring-audit tests (hermetic)."""
import random

from moonface.foundation.models import Candle
from moonface.signal.engine.calibration import BarRow, BookState, HypoTrade

H = 3_600_000
ALL_MODULES = ("m1_macro", "m2_breakout", "m2_ma_align", "m3_roc",
               "m4_pullback", "m5_funding", "m1_sweep", "m2_reclaim",
               "m3_divergence", "m4_fund_ct", "m5_oi_flush", "m6_stretch")


def _walk_series(n, seed=7, start=100.0):
    rng = random.Random(seed)
    out, price = [], start
    for i in range(n):
        drift = rng.uniform(-1.0, 1.5)
        o = price
        c = max(1.0, price + drift)
        hi = max(o, c) + rng.uniform(0.0, 0.8)
        lo = min(o, c) - rng.uniform(0.0, 0.8)
        out.append(Candle(i * H, o, hi, lo, c, 10.0))
        price = c
    return out


def _mk_row(i, pts):
    full = {m: 0 for m in ALL_MODULES}
    full.update(pts)
    signed = sum(full[m] for m in ("m1_macro", "m2_breakout", "m2_ma_align",
                                   "m3_roc", "m4_pullback", "m5_funding"))
    d = 1 if signed > 0 else (-1 if signed < 0 else 0)
    bs = BookState(direction=d, score=abs(signed), breadth=3, policy="ALLOW")
    return BarRow(index=i, ts_ms=i * H, macro_effective="NEUTRAL",
                  vol_state="normal", regime_trend=0, trend=bs,
                  revert=BookState(0, 0, 0, None), module_points=full,
                  sweep_wick=None, decision_action="WAIT",
                  decision_direction=0, decision_score=0)


def _mk_trade(i, score, net_r, direction=1):
    return HypoTrade(entry_index=i, exit_index=i + 3, entry_ts_ms=i * H,
                     exit_ts_ms=(i + 3) * H, book="trend",
                     direction=direction, score=score, breadth=3,
                     policy="ALLOW", macro_effective="NEUTRAL",
                     vol_state="normal", net_r=net_r, bars_held=3,
                     exit_reason="stop")


def _fixture(n=1200, seed=2):
    """m2_breakout carries ALL the signal; m4_pullback is pure noise;
    m1_macro is a constant +20 keeping the LOO direction stable. All trades
    LONG (the row direction is +1 by construction, so panel and rows agree)."""
    rng = random.Random(seed)
    rows_by_index, panel = {}, []
    for k in range(n):
        i = k * 35
        m2 = rng.choice((0, 20))
        m4 = rng.choice((0, 5, 10))
        row = _mk_row(i, {"m1_macro": 20, "m2_breakout": m2,
                          "m4_pullback": m4})
        rows_by_index[i] = row
        net_r = round(0.05 * m2 + rng.gauss(0.0, 0.3), 4)
        panel.append(_mk_trade(i, 20 + m2 + m4, net_r))
    return panel, rows_by_index
```

- [ ] **Step 2: Write the failing tests** — create `tests/test_engine_audit_loo.py`:

```python
"""LOO marginal contribution (spec §5.2): panel fixed, direction-changed bars
excluded; Δρ = ρ(LOO score) − ρ(current score) on the kept subset, per split."""
from moonface.signal.engine.audit import loo_analysis, loo_book_score

from tests.helpers_audit import _fixture, _mk_row


def test_loo_book_score_drops_one_module():
    row = _mk_row(0, {"m1_macro": 20, "m2_breakout": 20, "m4_pullback": 5})
    assert loo_book_score(row, "trend", "m2_breakout") == (1, 25)
    assert loo_book_score(row, "trend", "m1_macro") == (1, 25)
    # dropping from the OTHER book leaves the trend sum whole
    assert loo_book_score(row, "trend", "m1_sweep") == (1, 45)


def test_loo_classes_informative_vs_noise():
    panel, rows_by_index = _fixture()
    table = loo_analysis(panel, rows_by_index, "trend")
    m2 = table["m2_breakout"]["splits"]["pooled"]
    assert m2["class"] == "CONTRIBUTES"
    assert m2["delta_ci_95"][1] < 0
    assert table["m4_pullback"]["splits"]["pooled"]["class"] == "DEAD"
    assert table["m2_breakout"]["n_direction_changed"] == 0  # m1 anchors dir


def test_loo_reports_all_splits():
    panel, rows_by_index = _fixture()
    table = loo_analysis(panel, rows_by_index, "trend")
    assert set(table["m2_breakout"]["splits"]) == {"pooled", "LONG", "SHORT"}
    # fixture trades are all LONG -> LONG matches pooled, SHORT underpowered
    assert (table["m2_breakout"]["splits"]["LONG"]["class"]
            == table["m2_breakout"]["splits"]["pooled"]["class"])
    short = table["m2_breakout"]["splits"]["SHORT"]
    assert short["n_kept"] == 0
    assert short["class"] == "UNDERPOWERED"


def test_loo_underpowered_below_floor():
    panel, rows_by_index = _fixture(n=100)
    table = loo_analysis(panel, rows_by_index, "trend")
    assert table["m2_breakout"]["splits"]["pooled"]["class"] == "UNDERPOWERED"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_loo.py -q`
Expected: FAIL — `ImportError: cannot import name 'loo_analysis'`

- [ ] **Step 4: Append to `src/moonface/signal/engine/audit.py`:**

```python
def loo_book_score(row: BarRow, book: str, drop: str) -> tuple[int, int]:
    """(direction, score) of the book's signed sum without module `drop`."""
    s = sum(p for m, p in row.module_points.items()
            if m in BOOK_MODULES[book] and m != drop)
    return (1 if s > 0 else (-1 if s < 0 else 0)), abs(s)


def loo_analysis(panel: list[HypoTrade], rows_by_index: dict[int, BarRow],
                 book: str) -> dict:
    """Marginal contribution per module and split (spec §5.2, §7 evidence
    table). Panel membership is held fixed; bars where dropping the module
    flips or zeroes the book direction are excluded from that module's Δρ
    and counted (once, pre-split). Δρ CI is a PAIRED block bootstrap: each
    resample computes ρ(LOO) − ρ(base) on the same draw."""

    def _delta(sample: list[tuple[HypoTrade, int]]) -> float | None:
        base = spearman([float(t.score) for t, _ in sample],
                        [t.net_r for t, _ in sample])
        loo = spearman([float(s) for _, s in sample],
                       [t.net_r for t, _ in sample])
        if base is None or loo is None:
            return None
        return loo - base

    out: dict[str, dict] = {}
    for drop in BOOK_MODULES[book]:
        kept_all: list[tuple[HypoTrade, int]] = []
        changed = 0
        for t in panel:
            d, s = loo_book_score(rows_by_index[t.entry_index], book, drop)
            if d != t.direction:
                changed += 1
                continue
            kept_all.append((t, s))
        splits: dict[str, dict] = {}
        for split in _SPLITS:
            if split == "pooled":
                kept = kept_all
            else:
                want = 1 if split == "LONG" else -1
                kept = [(t, s) for t, s in kept_all if t.direction == want]
            delta = _delta(kept)
            ci = block_ci(kept, lambda p: p[0].entry_index, _delta)
            if len(kept) < PANEL_FLOOR or delta is None or ci is None:
                klass = "UNDERPOWERED"
            elif ci[1] < 0:
                klass = "CONTRIBUTES"   # removal hurts ordering
            elif ci[0] > 0:
                klass = "HARMFUL"       # removal improves ordering
            else:
                klass = "DEAD"
            splits[split] = {
                "n_kept": len(kept),
                "delta_rho": (round(delta, 4)
                              if delta is not None else None),
                "delta_ci_95": _ci_out(ci),
                "class": klass,
            }
        out[drop] = {"n_direction_changed": changed, "splits": splits}
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_loo.py tests/test_engine_audit_stats.py -q`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/audit.py tests/helpers_audit.py tests/test_engine_audit_loo.py
git diff --cached --stat
git commit -m "feat(audit): per-split leave-one-out marginal contribution with paired block-bootstrap CI"
```

---

### Task 4: Single-module conditional ordering

**Files:**
- Modify: `src/moonface/signal/engine/audit.py` (append)
- Test: `tests/test_engine_audit_conditional.py`

**Interfaces:**
- Consumes: `block_ci`, `_split_trades`, `BOOK_MODULES` (Task 2/3).
- Produces: `conditional_ordering(panel, rows_by_index, book) -> dict` — per module, per split: `{n, spearman_rho, rho_ci_95, status}` where x = trade.direction × module signed points at the entry bar (direction-aligned: positive supports the trade).

- [ ] **Step 1: Write the failing tests** — create `tests/test_engine_audit_conditional.py`:

```python
"""Per-module conditional ordering vs trade net R (spec §5.3) — unlike the
calibration IC table, which used fixed-horizon drift and stays SECONDARY."""
from moonface.signal.engine.audit import conditional_ordering

from tests.helpers_audit import _fixture


def test_conditional_ordering_informative_vs_noise():
    panel, rows_by_index = _fixture()
    table = conditional_ordering(panel, rows_by_index, "trend")
    m2 = table["m2_breakout"]["pooled"]
    assert m2["status"] == "ok"
    assert m2["rho_ci_95"][0] > 0            # informative module orders R
    m4 = table["m4_pullback"]["pooled"]
    assert m4["rho_ci_95"][0] < 0 < m4["rho_ci_95"][1]   # noise spans 0
    # constant module has zero rank variance -> rho None, reported not crashed
    assert table["m1_macro"]["pooled"]["spearman_rho"] is None


def test_conditional_ordering_reports_all_splits():
    panel, rows_by_index = _fixture()
    table = conditional_ordering(panel, rows_by_index, "trend")
    assert set(table["m2_breakout"]) == {"pooled", "LONG", "SHORT"}
    # fixture trades are all LONG -> SHORT split is empty and underpowered
    assert table["m2_breakout"]["SHORT"]["n"] == 0
    assert table["m2_breakout"]["SHORT"]["status"] == "UNDERPOWERED"
```

(`tests.helpers_audit` imports work because the root `conftest.py` puts the repo on `sys.path` — same mechanism as the existing `tests.helpers_consolidated`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_conditional.py -q`
Expected: FAIL — `ImportError: cannot import name 'conditional_ordering'`

- [ ] **Step 3: Append to `src/moonface/signal/engine/audit.py`:**

```python
def conditional_ordering(panel: list[HypoTrade],
                         rows_by_index: dict[int, BarRow],
                         book: str) -> dict:
    """ρ(direction-aligned module points, net R) per module and split
    (spec §5.3). Trade-outcome-based, so it is directly comparable with the
    book-level baseline, unlike the fixed-horizon IC table."""
    out: dict[str, dict] = {}
    for module in BOOK_MODULES[book]:
        per_split: dict[str, dict] = {}
        for split in _SPLITS:
            trades = _split_trades(panel, split)
            pairs = [
                (t, float(t.direction
                          * rows_by_index[t.entry_index].module_points[module]))
                for t in trades]

            def _stat(sample: list[tuple[HypoTrade, float]]) -> float | None:
                return spearman([x for _, x in sample],
                                [t.net_r for t, _ in sample])

            rho = _stat(pairs)
            ci = block_ci(pairs, lambda p: p[0].entry_index, _stat)
            per_split[split] = {
                "n": len(pairs),
                "spearman_rho": round(rho, 4) if rho is not None else None,
                "rho_ci_95": _ci_out(ci),
                "status": ("UNDERPOWERED" if len(pairs) < PANEL_FLOOR
                           else "ok"),
            }
        out[module] = per_split
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_conditional.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/audit.py tests/test_engine_audit_conditional.py
git diff --cached --stat
git commit -m "feat(audit): per-module conditional ordering vs trade net R"
```

---

### Task 5: Fitted upper bound (chrono split, NNLS + logistic, OOS ordering)

**Files:**
- Modify: `src/moonface/signal/engine/audit.py` (append)
- Test: `tests/test_engine_audit_fit.py`

**Interfaces:**
- Consumes: Tasks 2–4 helpers; `calibration.BarRow.module_points`.
- Produces:
  - `chrono_split(panel, rows) -> tuple[list[HypoTrade], list[HypoTrade], int, int]` — (train, test, boundary_index, dropped). Boundary = index of the row 60% through the scored rows; train trades exit strictly before it; test trades enter at/after boundary + 168; the rest are dropped.
  - `fit_nnls(X: list[list[float]], y: list[float], sweeps=200) -> list[float]` — nonnegative coordinate-descent least squares on the Gram matrix.
  - `fit_logistic(X, y01, iters=300, lr=0.1) -> tuple[list[float], float]` — projected-gradient logistic, feature weights clamped ≥ 0, intercept free.
  - `fitted_upper_bound(panel, rows, rows_by_index, book) -> dict` — `{train_n, test_n, boundary_index, dropped, status, fitters: {nnls_net_r, logistic_win}, current}`; each fitter: `{weights, degenerate, oos: {pooled/LONG/SHORT: {n, spearman_rho, rho_ci_95, status}}}`; `current` has the same `oos` shape for the frozen score.
  - Module constants: `TRAIN_FRACTION = 0.6`, `PURGE_BARS = BLOCK_BARS`, `NNLS_SWEEPS = 200`, `LOGIT_ITERS = 300`, `LOGIT_LR = 0.1`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_engine_audit_fit.py`:

```python
"""Fitted upper bound (spec §5.4): leakage-safe chrono split, pre-enumerated
stdlib fitters, OOS Spearman verdict metric. Known-ordering data must yield a
CI-clean positive OOS rho; pure noise must span 0 (fixed seeds, deterministic)."""
import random

from moonface.signal.engine.audit import (chrono_split, fit_logistic,
                                          fit_nnls, fitted_upper_bound)

from tests.helpers_audit import _fixture, _mk_row, _mk_trade


def _rows_list(rows_by_index):
    return [rows_by_index[i] for i in sorted(rows_by_index)]


def test_chrono_split_leakage_rules():
    panel, rows_by_index = _fixture()
    rows = _rows_list(rows_by_index)
    train, test, boundary, dropped = chrono_split(panel, rows)
    assert all(t.exit_index < boundary for t in train)
    assert all(t.entry_index >= boundary + 168 for t in test)
    assert dropped == len(panel) - len(train) - len(test)
    assert dropped > 0            # straddlers/gap entries exist by construction
    assert len(train) and len(test)


def test_fit_nnls_recovers_informative_weight():
    rng = random.Random(3)
    X, y = [], []
    for _ in range(2000):
        a, b = rng.gauss(0, 1), rng.gauss(0, 1)
        X.append([a, b])
        y.append(2.0 * a + rng.gauss(0, 0.1))
    w = fit_nnls(X, y)
    assert w[0] > 1.5
    assert w[1] < 0.2
    assert all(v >= 0 for v in w)
    assert fit_nnls(X, y) == w    # deterministic


def test_fit_logistic_nonnegative_and_ordered():
    rng = random.Random(4)
    X, y01 = [], []
    for _ in range(2000):
        a, b = rng.gauss(0, 1), rng.gauss(0, 1)
        X.append([a, b])
        y01.append(1.0 if a + rng.gauss(0, 0.5) > 0 else 0.0)
    w, _bias = fit_logistic(X, y01)
    assert w[0] > 0.2
    assert all(v >= 0 for v in w)


def test_fitted_upper_bound_known_ordering():
    panel, rows_by_index = _fixture(n=2400)
    fit = fitted_upper_bound(panel, _rows_list(rows_by_index),
                             rows_by_index, "trend")
    assert fit["status"] == "ok"
    for name in ("nnls_net_r", "logistic_win"):
        oos = fit["fitters"][name]["oos"]["pooled"]
        assert oos["rho_ci_95"][0] > 0        # CI-clean positive OOS
    assert fit["current"]["oos"]["pooled"]["rho_ci_95"][0] > 0


def test_fitted_upper_bound_pure_noise_spans_zero():
    rng = random.Random(5)
    rows_by_index, panel = {}, []
    for k in range(2400):
        i = k * 35
        m2 = rng.choice((0, 20))
        rows_by_index[i] = _mk_row(i, {"m1_macro": 20, "m2_breakout": m2})
        panel.append(_mk_trade(i, 20 + m2, round(rng.gauss(0, 1), 4)))
    fit = fitted_upper_bound(panel, _rows_list(rows_by_index),
                             rows_by_index, "trend")
    assert fit["status"] == "ok"
    for name in ("nnls_net_r", "logistic_win"):
        lo, hi = fit["fitters"][name]["oos"]["pooled"]["rho_ci_95"]
        assert lo <= 0 <= hi


def test_fitted_upper_bound_underpowered():
    panel, rows_by_index = _fixture(n=300)   # train/test below floor
    fit = fitted_upper_bound(panel, _rows_list(rows_by_index),
                             rows_by_index, "trend")
    assert fit["status"] == "UNDERPOWERED"
    assert "fitters" not in fit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_fit.py -q`
Expected: FAIL — `ImportError: cannot import name 'chrono_split'`

- [ ] **Step 3: Append to `src/moonface/signal/engine/audit.py`:**

```python
TRAIN_FRACTION = 0.6
PURGE_BARS = BLOCK_BARS
NNLS_SWEEPS = 200
LOGIT_ITERS = 300
LOGIT_LR = 0.1


def chrono_split(panel: list[HypoTrade], rows: list[BarRow],
                 ) -> tuple[list[HypoTrade], list[HypoTrade], int, int]:
    """Leakage-safe chronological split (spec §5.4): boundary at the bar 60%
    through the scored rows; train trades exit strictly before it; test trades
    enter at/after boundary + PURGE_BARS; straddlers and gap entries drop."""
    boundary = rows[int(TRAIN_FRACTION * len(rows))].index
    train = [t for t in panel if t.exit_index < boundary]
    test = [t for t in panel if t.entry_index >= boundary + PURGE_BARS]
    dropped = len(panel) - len(train) - len(test)
    return train, test, boundary, dropped


def _features(trades: list[HypoTrade], rows_by_index: dict[int, BarRow],
              book: str) -> list[list[float]]:
    mods = BOOK_MODULES[book]
    return [[float(t.direction
                   * rows_by_index[t.entry_index].module_points[m])
             for m in mods] for t in trades]


def _standardize_fit(X: list[list[float]]) -> tuple[list[float], list[float]]:
    n, k = len(X), len(X[0])
    means = [sum(row[a] for row in X) / n for a in range(k)]
    sds = []
    for a in range(k):
        var = sum((row[a] - means[a]) ** 2 for row in X) / n
        sds.append(math.sqrt(var) if var > 0 else 1.0)  # sd=0 -> no-op scale
    return means, sds


def _standardize_apply(X: list[list[float]], means: list[float],
                       sds: list[float]) -> list[list[float]]:
    return [[(row[a] - means[a]) / sds[a] for a in range(len(means))]
            for row in X]


def fit_nnls(X: list[list[float]], y: list[float],
             sweeps: int = NNLS_SWEEPS) -> list[float]:
    """Nonnegative least squares via coordinate descent on the Gram matrix
    (12 features max — the Gram precompute is the only O(n) pass)."""
    n, k = len(X), len(X[0])
    gram = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)]
            for a in range(k)]
    c = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    w = [0.0] * k
    for _ in range(sweeps):
        for a in range(k):
            if gram[a][a] == 0:
                w[a] = 0.0
                continue
            resid = c[a] - sum(gram[a][b] * w[b] for b in range(k) if b != a)
            w[a] = max(0.0, resid / gram[a][a])
    return w


def fit_logistic(X: list[list[float]], y01: list[float],
                 iters: int = LOGIT_ITERS, lr: float = LOGIT_LR,
                 ) -> tuple[list[float], float]:
    """Projected-gradient logistic regression: feature weights clamped >= 0
    (spec §5.4), intercept free. Deterministic (zero init, fixed schedule)."""
    n, k = len(X), len(X[0])
    w = [0.0] * k
    bias = 0.0
    for _ in range(iters):
        gw = [0.0] * k
        gb = 0.0
        for i in range(n):
            z = bias + sum(w[a] * X[i][a] for a in range(k))
            z = max(-35.0, min(35.0, z))
            err = 1.0 / (1.0 + math.exp(-z)) - y01[i]
            gb += err
            for a in range(k):
                gw[a] += err * X[i][a]
        bias -= lr * gb / n
        for a in range(k):
            w[a] = max(0.0, w[a] - lr * gw[a] / n)
    return w, bias


def normalize_weights(w: list[float]) -> tuple[list[float], bool]:
    """Sum-normalize to 100 (spec §5.4). All-zero fits are degenerate: the
    score is constant, spearman returns None, and the fitter cannot pass."""
    s = sum(w)
    if s <= 0:
        return [0.0] * len(w), True
    return [100.0 * v / s for v in w], False


def _oos_ordering(pairs: list[tuple[HypoTrade, float]]) -> dict:
    """OOS ordering of an arbitrary per-trade score, per split."""
    out: dict[str, dict] = {}
    for split in _SPLITS:
        if split == "pooled":
            sub = pairs
        else:
            want = 1 if split == "LONG" else -1
            sub = [(t, x) for t, x in pairs if t.direction == want]

        def _stat(sample: list[tuple[HypoTrade, float]]) -> float | None:
            return spearman([x for _, x in sample],
                            [t.net_r for t, _ in sample])

        rho = _stat(sub)
        ci = block_ci(sub, lambda p: p[0].entry_index, _stat)
        out[split] = {
            "n": len(sub),
            "spearman_rho": round(rho, 4) if rho is not None else None,
            "rho_ci_95": _ci_out(ci),
            "status": "UNDERPOWERED" if len(sub) < PANEL_FLOOR else "ok",
        }
    return out


def fitted_upper_bound(panel: list[HypoTrade], rows: list[BarRow],
                       rows_by_index: dict[int, BarRow], book: str) -> dict:
    """Could ANY nonnegative reweighting order outcomes OOS? (spec §5.4)"""
    train, test, boundary, dropped = chrono_split(panel, rows)
    result: dict = {"train_n": len(train), "test_n": len(test),
                    "boundary_index": boundary, "dropped": dropped}
    if len(train) < PANEL_FLOOR or len(test) < PANEL_FLOOR:
        result["status"] = "UNDERPOWERED"
        return result
    mods = BOOK_MODULES[book]
    means, sds = _standardize_fit(_features(train, rows_by_index, book))
    x_train = _standardize_apply(_features(train, rows_by_index, book),
                                 means, sds)
    x_test = _standardize_apply(_features(test, rows_by_index, book),
                                means, sds)
    fits = {
        "nnls_net_r": fit_nnls(x_train, [t.net_r for t in train]),
        "logistic_win": fit_logistic(
            x_train, [1.0 if t.net_r > 0 else 0.0 for t in train])[0],
    }
    result["fitters"] = {}
    for name, raw in fits.items():
        weights, degenerate = normalize_weights(raw)
        scores = [sum(weights[a] * x_test[i][a] for a in range(len(mods)))
                  for i in range(len(test))]
        result["fitters"][name] = {
            "weights": {m: round(weights[a], 2)
                        for a, m in enumerate(mods)},
            "degenerate": degenerate,
            "oos": _oos_ordering(list(zip(test, scores))),
        }
    result["current"] = {
        "oos": _oos_ordering([(t, float(t.score)) for t in test])}
    result["status"] = "ok"
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_fit.py -q`
Expected: PASS (6 tests). Note: these tests bootstrap several 1k-trade panels — expect ~1–2 minutes, not instant.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/audit.py tests/test_engine_audit_fit.py
git diff --cached --stat
git commit -m "feat(audit): chrono-split fitted upper bound with stdlib NNLS and logistic fitters"
```

---

### Task 6: Verdicts + report assembly (and one-line spec amendment)

**Files:**
- Modify: `src/moonface/signal/engine/audit.py` (append)
- Modify: `docs/research-log/specs/2026-07-05-scoring-audit-design.md` (§7, one clause)
- Test: `tests/test_engine_audit_report.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5; `calibration.scoring_pass/overlapping_panel/series_fingerprint`; `config.engine_hash`.
- Produces:
  - `book_verdict(fit_result: dict) -> str` — UNDERPOWERED / NO_SIGNAL_IN_ANY_WEIGHTING / CURRENT_WEIGHTS_ADEQUATE / WEIGHTS_MISCALIBRATED.
  - `build_audit_report(cfg, candles, warmup, deriv_by_index=None, stage=1, deriv_meta=None) -> dict` — the full JSON-serializable report (consumed by Task 8's CLI).

**Spec amendment (approved during plan review):** spec §7 rule 1 says "no **fitter** achieves CI-clean positive OOS ρ" — taken literally, current weights passing while both fitters fail would absurdly read "no signal in any weighting". The implementation treats "any weighting" as fitters ∪ current weights. Step 5 patches the spec sentence to match.

- [ ] **Step 1: Write the failing tests** — create `tests/test_engine_audit_report.py`:

```python
"""Verdict precedence (spec §7, as amended) and end-to-end report shape."""
from moonface.signal.engine.audit import (AUDIT_LABEL, book_verdict,
                                          build_audit_report)
from moonface.signal.engine.config import EngineConfig, engine_hash

from tests.helpers_audit import _walk_series


def _fit(cur_lo, fit_lo_a, fit_lo_b):
    def oos(lo):
        return {"oos": {"pooled": {"n": 1000, "spearman_rho": lo + 0.02,
                                   "rho_ci_95": [lo, lo + 0.05],
                                   "status": "ok"}}}
    return {"status": "ok",
            "fitters": {"nnls_net_r": oos(fit_lo_a),
                        "logistic_win": oos(fit_lo_b)},
            "current": oos(cur_lo)}


def test_verdict_precedence():
    assert book_verdict({"status": "UNDERPOWERED"}) == "UNDERPOWERED"
    # nothing clean-positive anywhere -> no signal in any weighting
    assert book_verdict(_fit(-0.1, -0.1, -0.1)) == "NO_SIGNAL_IN_ANY_WEIGHTING"
    # current clean-positive -> adequate, even if fitters also pass
    assert book_verdict(_fit(0.01, 0.05, -0.1)) == "CURRENT_WEIGHTS_ADEQUATE"
    # amended edge: current clean but fitters not -> still adequate
    assert book_verdict(_fit(0.01, -0.1, -0.1)) == "CURRENT_WEIGHTS_ADEQUATE"
    # fitter clean, current not -> miscalibrated
    assert book_verdict(_fit(-0.1, 0.01, -0.1)) == "WEIGHTS_MISCALIBRATED"


def test_build_audit_report_shape_on_synthetic_series():
    cfg = EngineConfig(lookback_bars=400)
    candles = _walk_series(700)
    report = build_audit_report(cfg, candles, warmup=380)
    assert report["engine_hash"] == engine_hash(cfg)
    assert report["label"] == AUDIT_LABEL
    assert report["stage"] == 1
    assert report["deriv"] is None
    assert set(report["books"]) == {"trend", "mean_revert"}
    trend = report["books"]["trend"]
    for key in ("panel_counts", "baseline", "loo", "conditional",
                "fitted_upper_bound", "verdict"):
        assert key in trend
    assert len(trend["loo"]) == 6                  # all trend modules present
    assert report["data"]["scored_bars"] == 700 - 380
    # tiny synthetic span -> everything underpowered, and that is a verdict
    assert trend["verdict"] == "UNDERPOWERED"
    import json
    json.dumps(report)                              # JSON-serializable
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_report.py -q`
Expected: FAIL — `ImportError: cannot import name 'book_verdict'`

- [ ] **Step 3: Append to `src/moonface/signal/engine/audit.py`** (and extend the calibration import at the top of the file to include `overlapping_panel`, `scoring_pass`, `series_fingerprint`, plus add `from moonface.signal.engine.config import EngineConfig, engine_hash` and `from moonface.foundation.models import Candle`):

```python
def _clean_positive(oos_block: dict | None) -> bool:
    if not oos_block:
        return False
    pooled = oos_block.get("oos", {}).get("pooled", {})
    ci = pooled.get("rho_ci_95")
    return bool(ci) and ci[0] > 0 and pooled.get("status") == "ok"


def book_verdict(fit_result: dict) -> str:
    """Spec §7 precedence (amended: 'any weighting' = fitters ∪ current)."""
    if fit_result.get("status") != "ok":
        return "UNDERPOWERED"
    current_ok = _clean_positive(fit_result.get("current"))
    fitter_ok = any(_clean_positive(f)
                    for f in fit_result.get("fitters", {}).values())
    if not current_ok and not fitter_ok:
        return "NO_SIGNAL_IN_ANY_WEIGHTING"
    if current_ok:
        return "CURRENT_WEIGHTS_ADEQUATE"
    return "WEIGHTS_MISCALIBRATED"


def build_audit_report(cfg: EngineConfig, candles: list[Candle], warmup: int,
                       deriv_by_index: dict | None = None, stage: int = 1,
                       deriv_meta: dict | None = None) -> dict:
    """Full audit report (spec §5, §7). Panel construction is calibration's,
    unchanged; deriv_by_index=None keeps Stage-1 price-core semantics."""
    rows = scoring_pass(cfg, candles, warmup, deriv_by_index=deriv_by_index)
    rows_by_index = {r.index: r for r in rows}
    books: dict[str, dict] = {}
    for book in ("trend", "mean_revert"):
        panel, counts = overlapping_panel(candles, cfg, rows, book)
        fit = fitted_upper_bound(panel, rows, rows_by_index, book)
        books[book] = {
            "panel_counts": counts,
            "baseline": baseline_ordering(panel),
            "loo": loo_analysis(panel, rows_by_index, book),
            "conditional": conditional_ordering(panel, rows_by_index, book),
            "fitted_upper_bound": fit,
            "verdict": book_verdict(fit),
        }
    return {
        "engine_hash": engine_hash(cfg),
        "label": AUDIT_LABEL,
        "stage": stage,
        "data": {
            "candles": len(candles),
            "scored_bars": len(rows),
            "first_scored_ts_ms": rows[0].ts_ms if rows else None,
            "last_ts_ms": candles[-1].timestamp_ms if candles else None,
            "fingerprint_sha256": series_fingerprint(candles),
            "lookback_bars": cfg.lookback_bars,
            "warmup": warmup,
        },
        "frozen_analysis_constants": {
            "block_bars": BLOCK_BARS, "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED, "panel_floor": PANEL_FLOOR,
            "train_fraction": TRAIN_FRACTION, "purge_bars": PURGE_BARS,
            "nnls_sweeps": NNLS_SWEEPS, "logit_iters": LOGIT_ITERS,
            "logit_lr": LOGIT_LR,
        },
        "deriv": deriv_meta,
        "books": books,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_report.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Amend spec §7 rule 1** — in `docs/research-log/specs/2026-07-05-scoring-audit-design.md`, replace:

```
1. **NO_SIGNAL_IN_ANY_WEIGHTING** — no fitter achieves CI-clean positive OOS
   ρ. The modules themselves lack signal; weights are exonerated.
```

with:

```
1. **NO_SIGNAL_IN_ANY_WEIGHTING** — neither any fitter nor the current
   weights achieve CI-clean positive OOS ρ. The modules themselves lack
   signal; weights are exonerated.
```

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/audit.py tests/test_engine_audit_report.py
git add -f docs/research-log/specs/2026-07-05-scoring-audit-design.md
git diff --cached --stat
git commit -m "feat(audit): book verdicts + report assembly; spec §7 no-signal clause covers current weights"
```

---

### Task 7: `deriv_history.py` — historical per-bar DerivSnapshots (Stage 2 data path)

**Files:**
- Create: `src/moonface/signal/engine/deriv_history.py`
- Test: `tests/test_deriv_history.py`

**Interfaces:**
- Consumes: `deriv.DerivSnapshot`, `deriv._percentile_of_last`, `deriv._oi_change_from_points`, `deriv.FUND_WINDOW_DAYS`; `foundation.series.fetch_metrics_history`; `research.universe_data.fetch_funding_rates`.
- Produces:
  - `DerivCoverage` dataclass: `scored_bars: int, funding_ok: int, oi_ok: int`, methods `funding_fraction() -> float`, `oi_fraction() -> float`.
  - `build_deriv_by_index(candles, warmup, archive_symbol, cache_dir, funding_points=None, oi_points=None) -> tuple[dict[int, DerivSnapshot], DerivCoverage]` — points injectable for hermetic tests; fetched from the cached loaders when `None`. `archive_symbol` is Vision/fapi form, e.g. `"BTCUSDT"`.

**Semantics (mirror live `fetch_deriv_snapshot` exactly, documented in pre-reg):** per bar `j`, `now_ms = candles[j].timestamp_ms + 3_600_000` (bar close — live evaluation runs just after close; `Candle.timestamp_ms` is the OPEN). Funding window `[now_ms − 30d, now_ms]` inclusive of the right edge (live fetches `[start, now+1)`); OI window `[now_ms − 8h, now_ms]`, change computed by the live `_oi_change_from_points` formula. One deliberate difference, recorded in the pre-reg: history uses 5-min Vision metrics where live uses 1h fapi points — same formula, finer grid.

- [ ] **Step 1: Write the failing tests** — create `tests/test_deriv_history.py`:

```python
"""Historical DerivSnapshot reconstruction (spec §6): live semantics, no
lookahead, coverage accounting. Hermetic — points injected, never fetched."""
from moonface.foundation.models import Candle
from moonface.signal.engine.deriv import DerivSnapshot
from moonface.signal.engine.deriv_history import (DerivCoverage,
                                                  build_deriv_by_index)

H = 3_600_000
D = 86_400_000


def _candles(n):
    return [Candle(i * H, 100.0, 101.0, 99.0, 100.0, 10.0)
            for i in range(n)]


def test_funding_percentile_matches_live_semantics():
    candles = _candles(24)
    # funding events every 8h; last event exactly AT bar-10 close is included
    close10 = candles[10].timestamp_ms + H
    funding = [(close10 - 16 * H, 0.01), (close10 - 8 * H, 0.03),
               (close10, 0.02)]
    out, cov = build_deriv_by_index(candles, warmup=10, archive_symbol="X",
                                    cache_dir="unused",
                                    funding_points=funding, oi_points=[])
    # percentile of last (0.02) among {0.01, 0.03, 0.02} -> 2/3
    assert abs(out[10].funding_pct - 100.0 * 2 / 3) < 1e-9
    assert cov.funding_ok >= 1


def test_no_lookahead_point_after_close_excluded():
    candles = _candles(24)
    close10 = candles[10].timestamp_ms + H
    out, _cov = build_deriv_by_index(
        candles, warmup=10, archive_symbol="X", cache_dir="unused",
        funding_points=[(close10 + 1, 0.05)], oi_points=[])
    assert out[10].funding_pct is None      # 1ms after close: invisible


def test_funding_window_is_30_days():
    candles = _candles(24)
    close10 = candles[10].timestamp_ms + H
    stale = [(close10 - 31 * D, 0.09), (close10, 0.02)]
    out, _cov = build_deriv_by_index(
        candles, warmup=10, archive_symbol="X", cache_dir="unused",
        funding_points=stale, oi_points=[])
    # the 31-day-old point fell out of the window: percentile over {0.02} only
    assert out[10].funding_pct == 100.0


def test_oi_change_6h_from_5min_points():
    candles = _candles(24)
    close10 = candles[10].timestamp_ms + H
    oi = ([(close10 - 7 * H, 1000.0)]
          + [(close10 - 6 * H + k * 300_000, 1000.0) for k in range(3)]
          + [(close10, 970.0)])
    out, cov = build_deriv_by_index(
        candles, warmup=10, archive_symbol="X", cache_dir="unused",
        funding_points=[], oi_points=oi)
    assert abs(out[10].oi_change_6h - (970.0 / 1000.0 - 1.0)) < 1e-9
    assert cov.oi_ok >= 1


def test_coverage_counts_scored_bars_only():
    candles = _candles(24)
    out, cov = build_deriv_by_index(
        candles, warmup=20, archive_symbol="X", cache_dir="unused",
        funding_points=[], oi_points=[])
    assert cov.scored_bars == 4
    assert cov.funding_fraction() == 0.0
    assert cov.oi_fraction() == 0.0
    assert set(out) == {20, 21, 22, 23}
    assert out[20] == DerivSnapshot(funding_pct=None, oi_change_6h=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_deriv_history.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.signal.engine.deriv_history'`

- [ ] **Step 3: Create `src/moonface/signal/engine/deriv_history.py`:**

```python
"""Historical per-bar DerivSnapshots for the scoring audit's Stage 2.

Reconstructs what live fetch_deriv_snapshot would have returned at each bar
close, from the repo's cached loaders: funding via research.universe_data
(fapi, whole-window cache), open interest via foundation.series Binance
Vision 5-min metrics (per-day cache). Live formulas are imported, not
reimplemented. One documented difference: live OI uses 1h fapi points,
history uses the 5-min Vision grid — same _oi_change_from_points formula.

Read-only diagnostic support; never used by the live engine path.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from moonface.foundation.models import Candle
from moonface.foundation.series import fetch_metrics_history
from moonface.research.universe_data import fetch_funding_rates
from moonface.signal.engine.deriv import (FUND_WINDOW_DAYS, DerivSnapshot,
                                          _oi_change_from_points,
                                          _percentile_of_last)

_HOUR_MS = 3_600_000
_DAY_MS = 86_400_000
OI_LOOKBACK_MS = 8 * _HOUR_MS   # live fetch window feeding the 6h change


@dataclass(frozen=True)
class DerivCoverage:
    scored_bars: int
    funding_ok: int
    oi_ok: int

    def funding_fraction(self) -> float:
        return self.funding_ok / self.scored_bars if self.scored_bars else 0.0

    def oi_fraction(self) -> float:
        return self.oi_ok / self.scored_bars if self.scored_bars else 0.0


def build_deriv_by_index(candles: list[Candle], warmup: int,
                         archive_symbol: str, cache_dir: str,
                         funding_points: list[tuple[int, float]] | None = None,
                         oi_points: list[tuple[int, float]] | None = None,
                         ) -> tuple[dict[int, DerivSnapshot], DerivCoverage]:
    """Per-bar snapshots for every scored bar (index >= warmup).

    now_ms per bar = open + 1h (bar close; live evaluates just after close).
    Funding window [now-30d, now], OI window [now-8h, now] — both inclusive
    of the right edge, mirroring live's [start, now+1) fetches. Missing data
    degrades to None fields exactly as live does; never imputed."""
    if funding_points is None or oi_points is None:
        span_start = (candles[warmup].timestamp_ms
                      - FUND_WINDOW_DAYS * _DAY_MS)
        span_end = candles[-1].timestamp_ms + _HOUR_MS + 1
        if funding_points is None:
            funding_points = fetch_funding_rates(
                archive_symbol, span_start, span_end, cache_dir)
        if oi_points is None:
            raw = fetch_metrics_history(archive_symbol, span_start,
                                        span_end, cache_dir)
            oi_points = [(ts, f["sum_open_interest"]) for ts, f in raw
                         if "sum_open_interest" in f]
    funding_points = sorted(funding_points)
    oi_points = sorted(oi_points)
    f_ts = [t for t, _ in funding_points]
    o_ts = [t for t, _ in oi_points]

    out: dict[int, DerivSnapshot] = {}
    funding_ok = oi_ok = 0
    for j in range(warmup, len(candles)):
        now_ms = candles[j].timestamp_ms + _HOUR_MS
        f_lo = bisect_left(f_ts, now_ms - FUND_WINDOW_DAYS * _DAY_MS)
        f_hi = bisect_right(f_ts, now_ms)
        pct = _percentile_of_last(funding_points[f_lo:f_hi])
        o_lo = bisect_left(o_ts, now_ms - OI_LOOKBACK_MS)
        o_hi = bisect_right(o_ts, now_ms)
        change = _oi_change_from_points(oi_points[o_lo:o_hi])
        if pct is not None:
            funding_ok += 1
        if change is not None:
            oi_ok += 1
        out[j] = DerivSnapshot(funding_pct=pct, oi_change_6h=change)
    coverage = DerivCoverage(scored_bars=len(candles) - warmup,
                             funding_ok=funding_ok, oi_ok=oi_ok)
    return out, coverage
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_deriv_history.py -q`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/deriv_history.py tests/test_deriv_history.py
git diff --cached --stat
git commit -m "feat(audit): historical DerivSnapshot reconstruction with live semantics and coverage accounting"
```

---

### Task 8: CLI `tools/engine_audit.py` (both stages, integrity gate)

**Files:**
- Create: `tools/engine_audit.py`
- Test: `tests/test_engine_audit_cli.py`

**Interfaces:**
- Consumes: `audit.build_audit_report` (Task 6), `deriv_history.build_deriv_by_index` (Task 7), `load_bundle`, `load_engine_config`.
- Produces: `run(argv) -> int` (0 ok; 2 mechanical failure), `build_parser()`. Mirrors `tools/engine_calibration.py` conventions (module-level import style, `--out` JSON with `indent=2, sort_keys=True`).

- [ ] **Step 1: Write the failing tests** — create `tests/test_engine_audit_cli.py`:

```python
"""Audit CLI: stage routing, mechanical-failure exits (spec §8), report file.
Hermetic — load_bundle and the deriv builder are monkeypatched."""
import json

from moonface.foundation.bundle import DataBundle
from moonface.signal.engine.deriv import DerivSnapshot
from moonface.signal.engine.deriv_history import DerivCoverage
import tools.engine_audit as cli

from tests.helpers_audit import H, _walk_series


def _patch_bundle(monkeypatch, n=700):
    candles = _walk_series(n)
    monkeypatch.setattr(cli, "load_bundle",
                        lambda *a, **kw: DataBundle(candles=candles,
                                                    funding=None, basis=None,
                                                    feature=None))
    return candles


def _base_args(tmp_path, stage="1"):
    return ["--stage", stage, "--start-ms", "0", "--end-ms", str(700 * H),
            "--warmup", "380", "--engine", "promotion/engine.json",
            "--lookback-bars", "400",
            "--out", str(tmp_path / "report.json")]


def test_stage1_writes_report(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    assert cli.run(_base_args(tmp_path)) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["stage"] == 1
    assert report["deriv"] is None
    assert set(report["books"]) == {"trend", "mean_revert"}


def test_truncated_data_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch, n=100)          # 100 candles <= warmup 380
    assert cli.run(_base_args(tmp_path)) == 2
    assert not (tmp_path / "report.json").exists()


def test_stage2_coverage_below_floor_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    monkeypatch.setattr(
        cli, "build_deriv_by_index",
        lambda *a, **kw: ({}, DerivCoverage(320, 320, 100)))  # oi 31%
    assert cli.run(_base_args(tmp_path, stage="2")) == 2
    assert not (tmp_path / "report.json").exists()


def test_stage2_coverage_ok_runs_and_records_meta(monkeypatch, tmp_path):
    candles = _patch_bundle(monkeypatch)
    snaps = {j: DerivSnapshot(funding_pct=50.0, oi_change_6h=0.0)
             for j in range(380, len(candles))}
    monkeypatch.setattr(
        cli, "build_deriv_by_index",
        lambda *a, **kw: (snaps, DerivCoverage(320, 320, 318)))
    assert cli.run(_base_args(tmp_path, stage="2")) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["stage"] == 2
    assert report["deriv"]["funding_coverage"] == 1.0
    assert report["deriv"]["coverage_floor"] == 0.90
```

Note: `--lookback-bars` is a CLI override the calibration CLI does not have; the audit CLI needs it so hermetic tests can run a small window against the real `promotion/engine.json` without touching that file. The registered runs do NOT pass it (frozen config value 6000 applies).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.engine_audit'`

- [ ] **Step 3: Create `tools/engine_audit.py`:**

```python
# tools/engine_audit.py
"""Read-only scoring component & weight audit CLI (both stages).

Spec: docs/research-log/specs/2026-07-05-scoring-audit-design.md; frozen
criteria: experiments/engine/SCORING_AUDIT_2026-07.md.

DIAGNOSTIC ONLY — never gates, never mutates state, never recommends a
constant change. Touches no frozen value; the v2.1 forward-paper clock is
unaffected.

Usage (Stage 1, registered):
  .venv/bin/python -m tools.engine_audit --stage 1 \
      --start-ms 1577836800000 --end-ms 1782316800000 \
      --out experiments/engine/audit_report_stage1.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json

from moonface.foundation.bundle import load_bundle
from moonface.signal.engine.audit import build_audit_report
from moonface.signal.engine.config import load_engine_config
from moonface.signal.engine.deriv_history import build_deriv_by_index

COVERAGE_FLOOR = 0.90


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-audit")
    p.add_argument("--stage", type=int, choices=(1, 2), required=True)
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000,
                   help="first scored bar has a full lookback window")
    p.add_argument("--coverage-floor", type=float, default=COVERAGE_FLOOR,
                   help="Stage-2 deriv integrity gate (spec §6)")
    p.add_argument("--lookback-bars", type=int, default=None,
                   help="test-only window override; registered runs omit it")
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    if args.lookback_bars is not None:
        cfg = dataclasses.replace(cfg, lookback_bars=args.lookback_bars)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms,
                         args.cache_dir)
    if len(bundle.candles) <= args.warmup:
        print(f"ERROR: {len(bundle.candles)} candles <= warmup "
              f"{args.warmup} — truncated data, refusing to run")
        return 2
    deriv_by_index = None
    deriv_meta = None
    if args.stage == 2:
        archive = cfg.asset["symbol"].split(":")[0].replace("/", "")
        deriv_by_index, cov = build_deriv_by_index(
            bundle.candles, args.warmup, archive, args.cache_dir)
        deriv_meta = {
            "archive_symbol": archive,
            "funding_coverage": round(cov.funding_fraction(), 4),
            "oi_coverage": round(cov.oi_fraction(), 4),
            "coverage_floor": args.coverage_floor,
        }
        if min(cov.funding_fraction(),
               cov.oi_fraction()) < args.coverage_floor:
            print(f"ERROR: deriv coverage below floor: {deriv_meta}")
            return 2
    report = build_audit_report(cfg, bundle.candles, args.warmup,
                                deriv_by_index=deriv_by_index,
                                stage=args.stage, deriv_meta=deriv_meta)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    print(text)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
```

(`EngineConfig` is a frozen dataclass — `src/moonface/signal/engine/config.py:17` — so `dataclasses.replace` is correct.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_audit_cli.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — no regressions anywhere (~800 tests)

- [ ] **Step 6: Commit**

```bash
git add tools/engine_audit.py tests/test_engine_audit_cli.py
git diff --cached --stat
git commit -m "feat(audit): engine_audit CLI with stage routing and Stage-2 deriv integrity gate"
```

---

### Task 9: Stage-1 pre-registration (frozen) + registered run + results

**Files:**
- Create: `experiments/engine/SCORING_AUDIT_2026-07.md`
- Create (by the run): `experiments/engine/audit_report_stage1.json`

**Interfaces:**
- Consumes: the complete Stage-1 toolchain (Tasks 1–6, 8).
- Produces: the frozen Stage-1 criteria doc and the one registered Stage-1 report.

- [ ] **Step 1: Write `experiments/engine/SCORING_AUDIT_2026-07.md`:**

```markdown
# v2 Scoring Component & Weight Audit (2026-07)

**STATUS: Stage-1 CRITERIA FROZEN (pre-run). Stage-1 results section empty
until the single registered run completes; criteria may not change
afterward. Stage-2 criteria are frozen in this file AFTER Stage-1 results
publish and BEFORE any deriv data is inspected.**

Spec: `docs/research-log/specs/2026-07-05-scoring-audit-design.md`
Tooling: `src/moonface/signal/engine/audit.py`, `tools/engine_audit.py`
Engine identity: frozen v2.1 hash
`4e35561fe6b7d639712e10f8b87d78b5cf0a6d629d9ccc2cac8d605909305a6a`. This
lane is READ-ONLY: no frozen constant, config, journal, or registration
text is touched; the forward-paper clock is unaffected. Findings feed a
separate human-gated v2.2 / expansion decision only.

## The two questions

Per book and per direction: (a) does each module contribute
outcome-ordering signal; (b) could ANY nonnegative reweighting achieve
out-of-sample ordering — i.e., are the hand-set weights the problem, or the
modules themselves?

## Stage 1 — registered run (frozen)

- Command: `.venv/bin/python -m tools.engine_audit --stage 1
  --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000
  --out experiments/engine/audit_report_stage1.json`
- Data: cached `BTC/USDT:USDT` 1h perp (`.backtest_cache`), 2020-01 →
  2026-06 — the calibration diagnostic's exact span; series fingerprint
  recorded in the report JSON.
- One run. Re-runs only for mechanical failure (non-zero exit, truncated
  data), never to revisit a completed result.

## Stage 1 — frozen criteria

Panel semantics identical to `CALIBRATION_DIAGNOSTIC_2026-07.md`
(overlapping panel, frozen exit discipline, extreme-vol excluded).
Inference: moving-block bootstrap, block 168 bars, 1000 draws, seed
20260704; power floor 200 events per split (below floor = UNDERPOWERED, no
classification).

- **Per-module class, per split (pooled/LONG/SHORT) — LOO Δρ = ρ without
  module − ρ with, paired bootstrap, direction-changed bars excluded and
  counted:** CONTRIBUTES = Δρ CI entirely < 0; HARMFUL = CI entirely > 0;
  DEAD = CI spans 0.
- **Fitted upper bound:** chronological split at the bar 60% through the
  scored span; train trades exit before the boundary; test trades enter ≥
  boundary + 168 bars; straddlers/gap entries dropped and counted. Fitters
  (both reported, none selected): NNLS of net R on direction-aligned
  standardized module points; nonnegative-clamped logistic of win. Weights
  sum-normalized to 100 (all-zero = degenerate, cannot pass). Verdict
  metric: OOS Spearman(fitted score, net R), block-bootstrap 95% CI, on the
  pooled test panel.
- **Book verdict (first match):** UNDERPOWERED (train or test below floor);
  NO_SIGNAL_IN_ANY_WEIGHTING (neither any fitter nor the current weights
  CI-clean positive OOS); CURRENT_WEIGHTS_ADEQUATE (current weights
  CI-clean positive OOS; fitter headroom reported, never verdict-changing);
  WEIGHTS_MISCALIBRATED (otherwise).
- **Reported, never gated:** per-direction baseline/conditional/OOS tables
  (the SHORT-decision evidence), LOO exclusion counts, split drop counts.

## Stage 1 assumptions

1. deriv=None: Stage 1 covers the PRICE-STRUCTURE core only (trend book
   caps at 85/100; revert book lacks m4_fund_ct and m5_oi_flush). The three
   deriv modules will report as all-zero columns (rho None) — expected, not
   findings.
2. Sub-threshold hypothetical trades are counterfactual, as in the
   calibration diagnostic; they measure ordering, not tradability.
3. Fitted weights are on STANDARDIZED features — not directly comparable to
   the engine's point weights; only the OOS ordering they achieve is
   verdict-bearing.

## What this audit can and cannot conclude

It can attribute weak score quality to weights vs modules, and provide
per-direction evidence for a future SHORT decision. It CANNOT validate an
edge, recommend constant changes, or trigger any engine action. Any v2.2 is
a separate human decision (new ENGINE_VERSION → hash → registration).

## Stage 1 — results (write once, after the registered run)

*(empty until the run completes)*

## Stage 2 — deriv-inclusive (criteria to be frozen post-Stage-1, pre-run)

Gate: `deriv_history` integrity — funding AND OI coverage ≥ 0.90 of scored
bars, else the CLI exits non-zero and Stage 2 does not run to verdict.
The full frozen Stage-2 criteria section is written after Stage-1 results
publish, blind to any deriv numbers (it may cite Stage-1 facts), and before
the Stage-2 command executes.
```

- [ ] **Step 2: Commit the frozen pre-registration (before the run)**

```bash
git add experiments/engine/SCORING_AUDIT_2026-07.md
git diff --cached --stat
git commit -m "docs(engine): freeze Stage-1 scoring-audit pre-registration"
```

- [ ] **Step 3: Execute the registered Stage-1 run (ONE run)**

Run: `.venv/bin/python -m tools.engine_audit --stage 1 --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 --out experiments/engine/audit_report_stage1.json`
Expected: exit 0, report JSON written. NOTE: ~100 block-bootstrap CIs over panels up to ~46k trades — expect several hours (order 3–8h) of pure-Python compute; run it in the background and wait for exit rather than holding a foreground timeout.

- [ ] **Step 4: Fill the Stage-1 results section** — transcribe from `audit_report_stage1.json` into the `## Stage 1 — results` section: per book — baseline ρ per split, the LOO classification table, conditional-ordering highlights, fitted-upper-bound OOS numbers (both fitters + current), drop/exclusion counts, and the book verdicts. State the verdict once; no interpretation beyond the frozen criteria.

- [ ] **Step 5: Commit the results**

```bash
git add experiments/engine/SCORING_AUDIT_2026-07.md experiments/engine/audit_report_stage1.json
git diff --cached --stat
git commit -m "docs(engine): Stage-1 scoring-audit registered run + results"
```

---

### Task 10: Stage-2 pre-registration freeze + registered run + results (GATED)

**GATE: do not start until Stage-1 results are committed (Task 9) — and write the frozen Stage-2 section BEFORE running any deriv command or inspecting any deriv data.**

**Files:**
- Modify: `experiments/engine/SCORING_AUDIT_2026-07.md` (Stage-2 section)
- Create (by the run): `experiments/engine/audit_report_stage2.json`

- [ ] **Step 1: Replace the Stage-2 stub section** in `experiments/engine/SCORING_AUDIT_2026-07.md` with the frozen criteria (verbatim template below; the only permitted edits are citations of published Stage-1 facts):

```markdown
## Stage 2 — deriv-inclusive registered run (CRITERIA FROZEN pre-run)

- Command: `.venv/bin/python -m tools.engine_audit --stage 2
  --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000
  --coverage-floor 0.90
  --out experiments/engine/audit_report_stage2.json`
- Integrity gate: funding AND OI coverage ≥ 0.90 of scored bars, else exit
  non-zero, no verdict; coverage numbers publish in the report either way.
- Historical deriv semantics: per-bar snapshot at bar close (open + 1h);
  funding percentile over trailing 30 days inclusive of close; OI 6h change
  from Binance Vision 5-min sum_open_interest via the live formula. The
  5-min-vs-1h grid difference from live is accepted and documented.
- Criteria: IDENTICAL to Stage 1 (same panel, floors, classes, fitters,
  verdict precedence), now over all 12 modules with real deriv columns.
- One run. Re-runs only for mechanical failure. This section was frozen
  before any deriv data was fetched or inspected.

## Stage 2 — results (write once, after the registered run)

*(empty until the run completes)*
```

- [ ] **Step 2: Commit the frozen Stage-2 section (before the run)**

```bash
git add experiments/engine/SCORING_AUDIT_2026-07.md
git diff --cached --stat
git commit -m "docs(engine): freeze Stage-2 scoring-audit criteria (pre-run, deriv-blind)"
```

- [ ] **Step 3: Execute the registered Stage-2 run (ONE run)**

Run: `.venv/bin/python -m tools.engine_audit --stage 2 --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 --coverage-floor 0.90 --out experiments/engine/audit_report_stage2.json`
Expected: exit 0 and report written — OR exit 2 with the coverage numbers printed (that outcome is itself a registered result: record it in the results section as INTEGRITY_FAIL with the printed coverage, and stop). First run downloads ~6 years of daily Vision metrics zips (cached thereafter); allow several hours end to end.

- [ ] **Step 4: Fill the Stage-2 results section** — same transcription discipline as Stage 1, plus the deriv coverage block and, per deriv module (m5_funding, m4_fund_ct, m5_oi_flush), its LOO class and conditional ordering per direction.

- [ ] **Step 5: Commit the results**

```bash
git add experiments/engine/SCORING_AUDIT_2026-07.md experiments/engine/audit_report_stage2.json
git diff --cached --stat
git commit -m "docs(engine): Stage-2 scoring-audit registered run + results"
```

---

## Verification (after all tasks)

- [ ] `.venv/bin/python -m pytest -q` — full suite green.
- [ ] `git log --oneline` shows one commit per task, no attribution trailers.
- [ ] Confirm read-only posture held: with `BASE` = the commit immediately before the Task-1 commit (find it via `git log --oneline`), `git diff BASE -- promotion/ journal/ experiments/engine/CONFLUENCE_V21_FORWARD_REGISTRATION.md src/moonface/signal/engine/confluence.py src/moonface/signal/engine/modules/` must be empty (the only engine-package change on this plan is the `scoring_pass` seam in `calibration.py`).
- [ ] Both report JSONs record `engine_hash = 4e35561f…` and the series fingerprint.
```
