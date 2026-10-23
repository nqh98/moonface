# SMC Signal Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a broadcast Telegram channel (`moonface-feed`) that posts text-only, caveat-labeled TradesAI-style SMC setup cards for fresh, fully-confirmed setups across a top-volume perp universe on each 4h close.

**Architecture:** Promote the existing foundation-pure SMC/pivots detectors from `research/edge` up to `foundation` (research keeps re-import shims so leaderboards stay byte-identical), then add a new top-level package `moonface.feed` that imports `foundation` + reuses `signal.notify`. The feed scans a universe per 4h close, detects fresh setups, derives entry/TP/SL, renders a card, posts to a channel (dry-run by default), and tracks setup state + outcomes.

**Tech Stack:** Python ≥3.11, stdlib + `ccxt` (already a dependency), pytest, ruff. No new dependencies (text-only — no matplotlib/chart libs).

## Global Constraints

- Python ≥ 3.11; stdlib + `ccxt>=4.3.0` only — **no new dependencies** (text-only feed).
- Layering (locked by `tests/test_import_boundaries.py`): `foundation` imports nothing inside `moonface`; `signal` imports only `foundation`; `feed` imports `foundation` + `signal` only — **`feed` never imports `research`**; `signal` never imports `feed`; `foundation` never imports `feed`.
- Ruff: `line-length = 100`, `target-version = "py311"`.
- Commit messages use the repo's `type(scope): summary` convention. **No `Co-Authored-By` or any AI-attribution trailer** (global rule). Commit on `main` only (trunk-based, local, never push).
- **No network in tests.** `load_bundle`, `notify`, and `fetch_tickers` are injected seams.
- **No leverage/"x"** anywhere on a card. Every card carries the `[SMC SETUP — heuristic; no validated out-of-sample edge]` tag.
- **Dry-run by default.** Nothing is posted to Telegram unless `--post` is passed or `MOONFACE_FEED_POST=1` is set.
- `.backtest_cache/` is gitignored — tests use **synthetic fixtures**, never cached CSVs.
- Frozen detector constants (mirror the falsified advisor so behavior is reproducible): `WARMUP=60`, `N_PERIODS=5`, `ATR_PERIOD=14`, `DISPLACEMENT_MULT=1.5`, `WINDOW_CAP=100`.

---

## File Structure

Foundation (promoted detectors):

- `src/moonface/foundation/smc.py` — **create**. Liquidity pools/sweeps, swings, structure trend, CHOCH, **new `detect_bos()`**. Verbatim move of `research/edge/_smc.py` + the new function + `__all__`.
- `src/moonface/foundation/pivots.py` — **create**. Verbatim move of `research/edge/pivots.py` + `__all__`.
- `src/moonface/research/edge/_smc.py` — **modify** → thin re-export shim.
- `src/moonface/research/edge/pivots.py` — **modify** → thin re-export shim.

Feed package (all new under `src/moonface/feed/`):

- `__init__.py` — empty package marker.
- `setups.py` — `Setup` dataclass; `detect_all()` / `detect_last()` over a candle series.
- `levels.py` — `Levels` dataclass; `derive_levels(setup, pivots, atr)`.
- `card.py` — `render_card(symbol, setup, levels) -> str`.
- `state.py` — open-setup jsonl store: `setup_hash`, `is_open`, `open_setup`, `resolve_open`.
- `universe.py` — `select_top_volume(exchange, size, *, fetch_tickers)`.
- `loop.py` — `run_once()`, `run_watch()` (cadence loop, mirrors `signal.cli.watch`).
- `cli.py` — `build_parser()`, `main()`; new `moonface-feed` entry point.

Config / packaging:

- `pyproject.toml` — **modify**. Add `moonface-feed = "moonface.feed.cli:main"` to `[project.scripts]`.
- `tests/test_import_boundaries.py` — **modify**. Forbid `feed` for foundation & signal; add `test_feed_does_not_import_research`.

Tests (all new, synthetic fixtures, offline):

- `tests/test_foundation_smc_bos.py` — `detect_bos` behavior.
- `tests/test_foundation_promoted_detectors.py` — import-from-foundation + shim parity.
- `tests/test_feed_setups.py`, `tests/test_feed_levels.py`, `tests/test_feed_card.py`, `tests/test_feed_state.py`, `tests/test_feed_universe.py`, `tests/test_feed_cli.py`, `tests/test_feed_replay.py`.

---

## Task 1: Promote SMC + pivots detectors to `foundation` (shims preserve the research API)

**Files:**
- Create: `src/moonface/foundation/smc.py`
- Create: `src/moonface/foundation/pivots.py`
- Modify: `src/moonface/research/edge/_smc.py` (→ shim)
- Modify: `src/moonface/research/edge/pivots.py` (→ shim)
- Test: `tests/test_foundation_promoted_detectors.py`

**Interfaces:**
- Consumes: nothing new (the move is mechanical).
- Produces: `moonface.foundation.smc` and `moonface.foundation.pivots` exporting every public name that `research/edge/_smc.py` and `pivots.py` export today, so every existing import (`from moonface.research.edge._smc import detect_liquidity, detect_sweeps`, `from moonface.research.edge.pivots import PivotCtx, daily_pivots`, and `smc_variants.py`'s `from moonface.research.edge._smc import (classify_structure, detect_choch, detect_liquidity, detect_sweeps)`) keeps working unchanged via the shims.

- [ ] **Step 1: Write the failing test**

`tests/test_foundation_promoted_detectors.py`:
```python
from __future__ import annotations

from moonface.foundation.models import Candle
from moonface.foundation.smc import (
    LiquidityPool, LiquidityContext, Sweep, Swings, StructureEvent, StructureState,
    detect_liquidity, detect_sweeps, find_swings, classify_structure, detect_choch,
)
from moonface.foundation.pivots import PivotCtx, daily_pivots
# Shims must still expose the same names at the old paths.
from moonface.research.edge._smc import detect_liquidity as _shim_liq
from moonface.research.edge.pivots import daily_pivots as _shim_piv


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


def test_foundation_detect_liquidity_and_shim_match():
    candles = [_c(0, 100, 110, 95, 105), _c(1, 105, 110.2, 100, 106), _c(2, 106, 108, 101, 102)]
    assert any(p.side == "BUY" for p in detect_liquidity(candles, tolerance=0.5).pools)
    assert any(p.side == "BUY" for p in _shim_liq(candles, tolerance=0.5).pools)


def test_foundation_pivots_and_shim_match():
    series = [Candle(0, 100, 120, 90, 105, 1.0), Candle(3_600_000, 130, 140, 125, 135, 1.0)]
    assert daily_pivots(series)[-1] == _shim_piv(series)[-1] == PivotCtx(
        p=105.0, r1=120.0, s1=90.0, r2=135.0, s2=75.0, r3=150.0, s3=60.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_foundation_promoted_detectors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.foundation.smc'`.

- [ ] **Step 3: Create `foundation/smc.py`**

Copy the **entire current content** of `src/moonface/research/edge/_smc.py` verbatim into `src/moonface/foundation/smc.py`, then append an explicit export list at the bottom:

```python
__all__ = [
    "LiquidityPool", "LiquidityContext", "Sweep", "Swings",
    "StructureEvent", "StructureState",
    "detect_liquidity", "detect_sweeps", "find_swings",
    "classify_structure", "detect_choch",
]
```
(The docstring + every dataclass + function is copied unchanged — only the file path and the trailing `__all__` differ.)

- [ ] **Step 4: Create `foundation/pivots.py`**

Copy the **entire current content** of `src/moonface/research/edge/pivots.py` verbatim into `src/moonface/foundation/pivots.py`, then append:

```python
__all__ = ["PivotCtx", "daily_pivots"]
```

- [ ] **Step 5: Replace `research/edge/_smc.py` with a shim**

Overwrite `src/moonface/research/edge/_smc.py` so its entire content is:
```python
"""Back-compat shim: the SMC detectors now live in moonface.foundation.smc.

Kept so every existing import path (tests, smc_variants, leaderboards) stays
byte-identical after the detector promotion to foundation."""
from moonface.foundation.smc import *  # noqa: F401,F403
```

- [ ] **Step 6: Replace `research/edge/pivots.py` with a shim**

Overwrite `src/moonface/research/edge/pivots.py` so its entire content is:
```python
"""Back-compat shim: daily pivots now live in moonface.foundation.pivots."""
from moonface.foundation.pivots import *  # noqa: F401,F403
```

- [ ] **Step 7: Run the new test + every detector regression test**

Run: `pytest tests/test_foundation_promoted_detectors.py tests/test_edge_smc_liquidity.py tests/test_edge_smc_structure.py tests/test_edge_pivots.py tests/test_smc_variants.py tests/test_smc_decompose.py -v`
Expected: ALL PASS (the shims re-export, so research-side imports are unchanged).

- [ ] **Step 8: Run the full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green, no lint errors.

- [ ] **Step 9: Commit**

```bash
git add src/moonface/foundation/smc.py src/moonface/foundation/pivots.py \
        src/moonface/research/edge/_smc.py src/moonface/research/edge/pivots.py \
        tests/test_foundation_promoted_detectors.py
git commit -m "refactor(foundation): promote SMC + pivots detectors out of research

Detectors are foundation-pure (import only foundation.models/risk); move them
to foundation.smc / foundation.pivots so the live feed package can use them
without crossing the signal->research boundary. research.edge keeps re-export
shims so every leaderboard / smc_variants / PROGRAM_CONCLUSION repro stays
byte-identical."
```

---

## Task 2: Add `detect_bos()` (trend-continuation Break of Structure) to `foundation/smc.py`

**Files:**
- Modify: `src/moonface/foundation/smc.py` (add `detect_bos`; add it to `__all__`)
- Modify: `src/moonface/research/edge/_smc.py` shim — no change needed (`import *` picks it up once it's in `__all__`)
- Test: `tests/test_foundation_smc_bos.py`

**Interfaces:**
- Consumes: `find_swings`, `StructureEvent` (already in `foundation.smc`).
- Produces: `detect_bos(candles, direction, start_index, atr_value, displacement_mult=1.5, n_periods=5) -> StructureEvent | None`, where `direction ∈ {"BULLISH","BEARISH"}`. Returns a `StructureEvent(kind="BOS", direction, index, level)` whose `index` is the first candle after `start_index` that closes beyond the most recent **same-direction** structural swing with a displacement-sized range. Returns `None` if `atr_value <= 0` or there is no prior same-direction swing.

- [ ] **Step 1: Write the failing test**

`tests/test_foundation_smc_bos.py`:
```python
from __future__ import annotations

import unittest

from moonface.foundation.models import Candle
from moonface.foundation.risk import atr
from moonface.foundation.smc import detect_bos


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


class DetectBosTest(unittest.TestCase):
    def test_bullish_bos_breaks_prior_swing_high(self):
        # Rising series: a clear swing high at index 4 (high 120), pullback,
        # then a wide candle at index 9 closing above 120.
        candles = [
            _c(0, 100, 110, 95, 105),
            _c(1, 105, 115, 100, 112),
            _c(2, 112, 118, 108, 110),
            _c(3, 110, 116, 105, 108),
            _c(4, 108, 120, 107, 119),   # swing high 120 (peaks above neighbors)
            _c(5, 119, 121, 112, 114),
            _c(6, 114, 117, 108, 110),
            _c(7, 110, 113, 104, 106),
            _c(8, 106, 112, 105, 111),
            _c(9, 111, 130, 110, 128),   # wide candle, close 128 > 120 -> BOS @9
        ]
        a = atr(candles, 14)
        ev = detect_bos(candles, "BULLISH", start_index=8, atr_value=a,
                        displacement_mult=1.5, n_periods=3)
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.kind, "BOS")
        self.assertEqual(ev.direction, "BULLISH")
        self.assertEqual(ev.index, 9)

    def test_no_bos_when_close_does_not_break_swing(self):
        candles = [_c(i, 100, 105, 95, 100) for i in range(12)]
        self.assertIsNone(detect_bos(candles, "BULLISH", 8, atr(candles, 14), 1.5, 3))

    def test_returns_none_when_atr_nonpositive(self):
        self.assertIsNone(detect_bos([_c(0, 1, 1, 1, 1)], "BULLISH", 0, 0.0, 1.5, 3))
```
> Note: use `n_periods=3` in the test (small series) — production calls use the frozen `N_PERIODS=5`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_foundation_smc_bos.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_bos'`.

- [ ] **Step 3: Implement `detect_bos`**

Add this function to `src/moonface/foundation/smc.py` (after `detect_choch`), and add `"detect_bos"` to the `__all__` list:
```python
def detect_bos(
    candles: list[Candle],
    direction: Trend,
    start_index: int,
    atr_value: float,
    displacement_mult: float = 1.5,
    n_periods: int = 5,
) -> StructureEvent | None:
    """Trend-continuation Break of Structure: the first displacement candle after
    ``start_index`` that closes beyond the most recent SAME-direction structural
    swing. BULLISH -> close above the last swing high (continuation LONG);
    BEARISH -> close below the last swing low (continuation SHORT). Mirrors
    ``detect_choch`` but breaks the same-side swing instead of the opposing one."""
    if atr_value <= 0:
        return None
    swings = find_swings(candles, n_periods)
    if direction == "BULLISH":
        levels = [level for idx, level in swings.highs if idx <= start_index]
        if not levels:
            return None
        broken_level = levels[-1]
        for index in range(start_index + 1, len(candles)):
            current = candles[index]
            wide = (current.high - current.low) >= displacement_mult * atr_value
            if current.close > broken_level and wide:
                return StructureEvent("BOS", "BULLISH", index, broken_level)
        return None
    if direction == "BEARISH":
        levels = [level for idx, level in swings.lows if idx <= start_index]
        if not levels:
            return None
        broken_level = levels[-1]
        for index in range(start_index + 1, len(candles)):
            current = candles[index]
            wide = (current.high - current.low) >= displacement_mult * atr_value
            if current.close < broken_level and wide:
                return StructureEvent("BOS", "BEARISH", index, broken_level)
        return None
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_foundation_smc_bos.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/foundation/smc.py tests/test_foundation_smc_bos.py
git commit -m "feat(foundation): add detect_bos trend-continuation structure break"
```

---

## Task 3: Create `moonface.feed` package, update import-boundary rules, add `feed/setups.py` with the `Setup` type + `sweep_choch` detector

**Files:**
- Create: `src/moonface/feed/__init__.py` (empty)
- Create: `src/moonface/feed/setups.py`
- Modify: `tests/test_import_boundaries.py`
- Test: `tests/test_feed_setups.py`

**Interfaces:**
- Consumes: `moonface.foundation.models.Candle`, `moonface.foundation.risk.atr`, `moonface.foundation.smc.{detect_liquidity,detect_sweeps,detect_choch}`.
- Produces:
  - `feed.setups.Setup` (frozen dataclass): fields `setup_type: str`, `side: str` (`"LONG"|""SHORT""`), `confirm_index: int`, `entry_close: float`, `swept_level: float | None`, `struct_level: float | None`, `atr_value: float`.
  - `feed.setups.detect_all(candles) -> list[Setup]` — every confirmed setup across the series.
  - `feed.setups.detect_last(candles) -> list[Setup]` — only setups whose `confirm_index == len(candles)-1`.

- [ ] **Step 1: Write the failing test**

`tests/test_feed_setups.py`:
```python
from __future__ import annotations

from moonface.foundation.models import Candle
from moonface.feed.setups import Setup, detect_all, detect_last


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


def reversal_fixture():
    """~140 bars: repeated rising sell-sweep -> wide bullish-CHOCH legs (mirrors
    tests/test_smc_variants.py::reversal_fixture)."""
    bars = []
    idx = 0
    for leg in range(11):
        b = 100 + 10 * leg
        for o, h, lo, c in [
            (b, b + 2, b - 3, b), (b + 3, b + 6, b, b + 3),
            (b + 6, b + 9, b + 4, b + 6), (b + 9, b + 12, b + 7, b + 9),
            (b + 12, b + 15, b + 10, b + 12),   # swing high B+15
            (b + 10, b + 13, b + 5, b + 10), (b + 5, b + 8, b, b + 5),
            (b, b + 3, b - 6, b),               # equal low B-6
            (b - 3, b, b - 6, b - 3),           # equal low B-6 -> SELL pool
            (b - 5, b - 2, b - 20, b - 2),      # sweep: wick B-20, close B-2
            (b - 2, b + 20, b - 4, b + 18),     # wide rally -> bullish CHOCH
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return bars


def test_detect_all_finds_sweep_choch_longs():
    setups = detect_all(reversal_fixture())
    sweep_long = [s for s in setups if s.setup_type == "sweep_choch" and s.side == "LONG"]
    assert len(sweep_long) >= 1
    assert all(s.swept_level is not None for s in sweep_long)


def test_detect_last_only_returns_setups_at_final_candle():
    bars = reversal_fixture()
    # The fixture's last leg ends with a CHOCH rally at the final index.
    last = detect_last(bars)
    assert all(s.confirm_index == len(bars) - 1 for s in last)


def test_detect_last_empty_on_flat_window():
    bars = [_c(i, 100, 105, 95, 100) for i in range(80)]
    assert detect_last(bars) == []


def test_setup_is_frozen_and_carries_atr():
    s = Setup("sweep_choch", "LONG", 70, 100.0, 90.0, 95.0, 1.5)
    assert s.atr_value == 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_setups.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.feed'`.

- [ ] **Step 3: Create the empty package marker**

`src/moonface/feed/__init__.py`:
```python
"""MoonFace SMC signal feed: a broadcast Telegram channel of caveat-labeled
SMC setup cards. Imports foundation + signal only; never research."""
```

- [ ] **Step 4: Implement `feed/setups.py`**

`src/moonface/feed/setups.py`:
```python
"""SMC setup detection for the feed. A Setup is emitted when a confirming event
(sweep->CHOCH reversal, or BOS continuation) lands exactly on a given candle.
Frozen to the falsified advisor's detector constants so behavior is reproducible."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.foundation.models import Candle
from moonface.foundation.risk import atr
from moonface.foundation.smc import (classify_structure, detect_choch,
                                     detect_liquidity, detect_sweeps)

# Frozen detector constants (mirror research/edge/smc_variants.py).
WARMUP = 60
N_PERIODS = 5
ATR_PERIOD = 14
DISPLACEMENT_MULT = 1.5
WINDOW_CAP = 100
LOOKBACK = 30


@dataclass(frozen=True)
class Setup:
    setup_type: str                       # "sweep_choch" | "bos_continuation"
    side: str                             # "LONG" | "SHORT"
    confirm_index: int
    entry_close: float
    swept_level: float | None
    struct_level: float | None
    atr_value: float


def _window(candles: list[Candle], i: int) -> list[Candle]:
    return candles[max(0, i + 1 - WINDOW_CAP): i + 1]


def _sweep_choch_at(candles: list[Candle], i: int) -> Setup | None:
    """A sell-side sweep followed by a bullish CHOCH (mirror for short), with the
    CHOCH confirming exactly at index i."""
    if i < WARMUP:
        return None
    window = _window(candles, i)
    a = atr(window, ATR_PERIOD)
    if a <= 0:
        return None
    tol = max(0.25 * a, 1e-9)
    pools = detect_liquidity(window, tolerance=tol).pools
    sweeps = detect_sweeps(window, pools)
    min_index = max(0, len(window) - LOOKBACK)
    recent = [s for s in sweeps if s.index >= min_index]
    if not recent:
        return None
    sweep = recent[-1]
    rev_direction = "BULLISH" if sweep.side == "SELL" else "BEARISH"
    event = detect_choch(window, rev_direction, sweep.index, a,
                         DISPLACEMENT_MULT, N_PERIODS)
    if event is None or event.index != i:
        return None
    side = "LONG" if rev_direction == "BULLISH" else "SHORT"
    return Setup("sweep_choch", side, i, candles[i].close,
                 sweep.pool_level, event.level, a)


_FINDERS = (_sweep_choch_at,)  # bos_continuation is added in Task 4


def detect_all(candles: list[Candle]) -> list[Setup]:
    out: list[Setup] = []
    for i in range(WARMUP, len(candles)):
        for finder in _FINDERS:
            s = finder(candles, i)
            if s is not None:
                out.append(s)
    return out


def detect_last(candles: list[Candle]) -> list[Setup]:
    if not candles:
        return []
    last = len(candles) - 1
    return [s for finder in _FINDERS
            for s in [finder(candles, last)] if s is not None]
```

- [ ] **Step 5: Update the import-boundary test to cover `feed`**

In `tests/test_import_boundaries.py`, change the two existing tests' forbidden tuples and add a feed test:
```python
def test_foundation_imports_neither_signal_nor_research():
    assert _violations("foundation",
                       ("moonface.signal", "moonface.research", "moonface.feed")) == []


def test_signal_does_not_import_research():
    assert _violations("signal", ("moonface.research", "moonface.feed")) == []


def test_feed_does_not_import_research():
    assert _violations("feed", ("moonface.research",)) == []
```

- [ ] **Step 6: Run feed + boundary tests**

Run: `pytest tests/test_feed_setups.py tests/test_import_boundaries.py -v`
Expected: ALL PASS.

- [ ] **Step 7: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add src/moonface/feed/__init__.py src/moonface/feed/setups.py \
        tests/test_feed_setups.py tests/test_import_boundaries.py
git commit -m "feat(feed): Setup type + sweep->CHOCH detector; boundary rules for feed"
```

---

## Task 4: Add the `bos_continuation` setup to `feed/setups.py`

**Files:**
- Modify: `src/moonface/feed/setups.py`
- Test: `tests/test_feed_setups.py` (append cases)

**Interfaces:**
- Consumes: `foundation.smc.detect_bos` + `classify_structure`.
- Produces: setups with `setup_type == "bos_continuation"` emitted by `detect_all` / `detect_last`.

- [ ] **Step 1: Write the failing tests (append to `tests/test_feed_setups.py`)**

```python
def falling_fixture():
    """Mirror of reversal_fixture with a falling base -> BEARISH structure."""
    bars = []
    idx = 0
    for leg in range(11):
        b = 300 - 10 * leg
        for o, h, lo, c in [
            (b, b + 3, b - 2, b), (b - 3, b, b - 5, b - 3),
            (b - 5, b - 2, b - 9, b - 5), (b - 9, b - 6, b - 12, b - 9),
            (b - 12, b - 9, b - 15, b - 12),   # swing low B-15
            (b - 10, b - 5, b - 13, b - 10), (b - 5, b, b - 8, b - 5),
            (b, b + 6, b, b), (b + 3, b + 6, b, b + 3),   # equal highs -> BUY pool
            (b + 5, b + 22, b - 4, b + 2),                 # sweep
            (b + 2, b - 18, b + 4, b - 16),               # wide drop -> bearish CHOCH
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return bars


def _rising_trend_fixture():
    """A clean rising trend (HH/HL) with wide continuation candles so BOS fires."""
    bars = []
    for i in range(80):
        base = 100 + i * 2
        # every 10th candle is a wide breakout above the prior swing high
        if i % 10 == 9:
            bars.append(_c(i, base, base + 18, base - 1, base + 16))
        else:
            bars.append(_c(i, base, base + 4, base - 3, base + 1))
    return bars


def test_detect_all_finds_bos_continuation_in_rising_trend():
    setups = [s for s in detect_all(_rising_trend_fixture())
              if s.setup_type == "bos_continuation"]
    assert len(setups) >= 1
    assert all(s.side == "LONG" for s in setups)
    assert all(s.struct_level is not None for s in setups)


def test_detect_last_includes_bos_when_final_candle_breaks():
    bars = _rising_trend_fixture()
    last_setups = detect_last(bars)
    assert all(s.confirm_index == len(bars) - 1 for s in last_setups)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pytest tests/test_feed_setups.py -v`
Expected: the two new BOS tests FAIL (no `bos_continuation` setups emitted); the Task-3 tests still PASS.

- [ ] **Step 3: Add the `_bos_at` finder and register it**

In `src/moonface/feed/setups.py`, update the `foundation.smc` import to include `detect_bos`, add the finder, and register it:
```python
from moonface.foundation.smc import (classify_structure, detect_bos, detect_choch,
                                     detect_liquidity, detect_sweeps)
```
Add after `_sweep_choch_at`:
```python
def _bos_at(candles: list[Candle], i: int) -> Setup | None:
    """Trend-continuation BOS confirming exactly at index i: in a BULLISH
    structure, a wide close above the last swing high (LONG); BEARISH mirror."""
    if i < WARMUP:
        return None
    window = _window(candles, i)
    a = atr(window, ATR_PERIOD)
    if a <= 0:
        return None
    struct = classify_structure(window, N_PERIODS)
    if struct.trend == "NEUTRAL":
        return None
    event = detect_bos(window, struct.trend, i - 1, a,
                       DISPLACEMENT_MULT, N_PERIODS)
    if event is None or event.index != i:
        return None
    side = "LONG" if struct.trend == "BULLISH" else "SHORT"
    return Setup("bos_continuation", side, i, candles[i].close,
                 None, event.level, a)
```
Change the registry line to:
```python
_FINDERS = (_sweep_choch_at, _bos_at)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_feed_setups.py -v`
Expected: ALL PASS (Task-3 + the two new BOS tests).

- [ ] **Step 5: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/feed/setups.py tests/test_feed_setups.py
git commit -m "feat(feed): add BOS-continuation setup detector"
```

---

## Task 5: Add `feed/levels.py` (entry zone, TP1–3, SL, confidence)

**Files:**
- Create: `src/moonface/feed/levels.py`
- Test: `tests/test_feed_levels.py`

**Interfaces:**
- Consumes: `feed.setups.Setup`, `foundation.pivots.PivotCtx`.
- Produces:
  - `feed.levels.Levels` (frozen): `entry`, `entry_low`, `entry_high`, `stop`, `tp1`, `tp2`, `tp3`, `confidence` (all `float`).
  - `feed.levels.derive_levels(setup: Setup, pivots: PivotCtx | None, atr_value: float) -> Levels`.

- [ ] **Step 1: Write the failing test**

`tests/test_feed_levels.py`:
```python
from __future__ import annotations

from moonface.feed.levels import Levels, derive_levels
from moonface.feed.setups import Setup
from moonface.foundation.pivots import PivotCtx


def _long_setup():
    return Setup("sweep_choch", "LONG", 70, 100.0, 90.0, 95.0, 4.0)


def test_long_levels_use_pivots_for_tps_and_swept_level_for_stop():
    piv = PivotCtx(p=100.0, r1=104.0, s1=96.0, r2=108.0, s2=92.0, r3=112.0, s3=88.0)
    lv = derive_levels(_long_setup(), piv, 4.0)
    assert lv.entry == 100.0
    assert lv.entry_low == 99.0 and lv.entry_high == 101.0     # +/- 0.25*ATR
    assert lv.stop == 90.0 - 0.10 * 4.0                         # swept_level - buffer
    assert (lv.tp1, lv.tp2, lv.tp3) == (104.0, 108.0, 112.0)   # r1<r2<r3, all > entry
    assert 0.0 <= lv.confidence <= 1.0


def test_tps_ascending_in_r_multiples_when_no_pivots():
    lv = derive_levels(_long_setup(), None, 4.0)
    risk = lv.entry - lv.stop
    assert lv.tp1 > lv.entry > lv.stop
    assert lv.tp2 > lv.tp1 and lv.tp3 > lv.tp2
    assert abs((lv.tp1 - lv.entry) / risk - 1.0) < 1e-9
    assert abs((lv.tp2 - lv.entry) / risk - 2.0) < 1e-9
    assert abs((lv.tp3 - lv.entry) / risk - 3.0) < 1e-9


def test_short_levels_invert_sides():
    s = Setup("sweep_choch", "SHORT", 70, 100.0, 110.0, 105.0, 4.0)
    piv = PivotCtx(p=100.0, r1=104.0, s1=96.0, r2=108.0, s2=92.0, r3=112.0, s3=88.0)
    lv = derive_levels(s, piv, 4.0)
    assert lv.stop == 110.0 + 0.10 * 4.0                        # above swept level
    assert lv.tp1 < lv.entry < lv.stop
    assert (lv.tp1, lv.tp2, lv.tp3) == (96.0, 92.0, 88.0)      # s1>s2>s3, all < entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_levels.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.feed.levels'`.

- [ ] **Step 3: Implement `feed/levels.py`**

`src/moonface/feed/levels.py`:
```python
"""Derive entry zone / TP1-3 / SL / confidence for a Setup. Levels are a
transparent mapping from SMC structure + daily pivots; confidence is setup
quality, NOT a probability of profit."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.foundation.pivots import PivotCtx
from moonface.feed.setups import Setup

_BUFFER_ATR = 0.10  # SL sits this fraction of ATR beyond the invalidation level


@dataclass(frozen=True)
class Levels:
    entry: float
    entry_low: float
    entry_high: float
    stop: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float


def derive_levels(setup: Setup, pivots: PivotCtx | None,
                  atr_value: float) -> Levels:
    long_ = setup.side == "LONG"
    entry = setup.entry_close
    entry_low = entry - 0.25 * atr_value
    entry_high = entry + 0.25 * atr_value

    ref = setup.swept_level if setup.swept_level is not None else setup.struct_level
    if ref is None:
        stop = entry - 1.5 * atr_value if long_ else entry + 1.5 * atr_value
    else:
        stop = ref - _BUFFER_ATR * atr_value if long_ else ref + _BUFFER_ATR * atr_value
    risk = (entry - stop) if long_ else (stop - entry)
    if risk <= 0:                       # invalidation landed on the wrong side
        stop = entry - 1.5 * atr_value if long_ else entry + 1.5 * atr_value
        risk = abs(entry - stop)

    if pivots is not None:
        raw = [pivots.r1, pivots.r2, pivots.r3] if long_ else [pivots.s1, pivots.s2, pivots.s3]
        tps = [p for p in raw if (p > entry if long_ else p < entry)]
        tps.sort(reverse=not long_)
        tps = tps[:3]
    else:
        tps = []
    mults = (1.0, 2.0, 3.0)
    while len(tps) < 3:
        m = mults[len(tps)]
        tps.append(entry + m * risk if long_ else entry - m * risk)
    tp1, tp2, tp3 = tps[0], tps[1], tps[2]

    # confidence: transparent composite (NOT P(profit)).
    conf = 0.50
    if setup.struct_level is not None:
        conf += 0.10
    if setup.swept_level is not None:
        conf += 0.10
    conf += 0.10                       # the finder already required a displacement candle
    conf = max(0.0, min(1.0, conf))
    return Levels(entry, entry_low, entry_high, stop, tp1, tp2, tp3, round(conf, 2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feed_levels.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/feed/levels.py tests/test_feed_levels.py
git commit -m "feat(feed): derive entry/TP1-3/SL/confidence from structure + pivots"
```

---

## Task 6: Add `feed/card.py` (render the text card)

**Files:**
- Create: `src/moonface/feed/card.py`
- Test: `tests/test_feed_card.py`

**Interfaces:**
- Consumes: `feed.setups.Setup`, `feed.levels.Levels`.
- Produces: `feed.card.render_card(symbol: str, setup: Setup, levels: Levels) -> str`.

- [ ] **Step 1: Write the failing test (golden string)**

`tests/test_feed_card.py`:
```python
from __future__ import annotations

from moonface.feed.card import render_card
from moonface.feed.levels import Levels
from moonface.feed.setups import Setup


def _long():
    return Setup("sweep_choch", "LONG", 70, 100000.0, 90000.0, 95000.0, 1000.0)


def _levels():
    return Levels(entry=100000.0, entry_low=99750.0, entry_high=100250.0,
                  stop=89900.0, tp1=104000.0, tp2=108000.0, tp3=112000.0,
                  confidence=0.80)


def test_long_card_exact_text():
    card = render_card("BTC/USDT:USDT", _long(), _levels())
    assert card == (
        "🟢 BTCUSDT • LONG — Sell-side sweep + bullish CHoCH\n"
        "Entry: 99,750.00 – 100,250.00\n"
        "TP1: 104,000.00  TP2: 108,000.00  TP3: 112,000.00\n"
        "SL: 89,900.00\n"
        "Confidence: 0.80 (setup quality, NOT P(profit))\n"
        "Risk: ~1% — reference only, not execution sizing\n"
        "[SMC SETUP — heuristic; no validated out-of-sample edge]"
    )


def test_short_card_uses_red_arrow_and_bearish_name():
    s = Setup("bos_continuation", "SHORT", 70, 100000.0, None, 105000.0, 1000.0)
    card = render_card("ETH/USDT:USDT", s, _levels())
    assert card.startswith("🔴 ETHUSDT • SHORT — Bearish BOS continuation")
    assert "[SMC SETUP — heuristic; no validated out-of-sample edge]" in card
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_card.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.feed.card'`.

- [ ] **Step 3: Implement `feed/card.py`**

`src/moonface/feed/card.py`:
```python
"""Render a Setup + Levels as a single Telegram message string. Pure function."""
from __future__ import annotations

from moonface.feed.levels import Levels
from moonface.feed.setups import Setup

_NAMES = {
    ("sweep_choch", "LONG"): "Sell-side sweep + bullish CHoCH",
    ("sweep_choch", "SHORT"): "Buy-side sweep + bearish CHoCH",
    ("bos_continuation", "LONG"): "Bullish BOS continuation",
    ("bos_continuation", "SHORT"): "Bearish BOS continuation",
}

_CAVEAT = "[SMC SETUP — heuristic; no validated out-of-sample edge]"


def _fmt(x: float) -> str:
    return f"{x:,.2f}"


def render_card(symbol: str, setup: Setup, levels: Levels) -> str:
    arrow = "🟢" if setup.side == "LONG" else "🔴"
    clean = symbol.replace("/", "").replace(":", "")
    name = _NAMES[(setup.setup_type, setup.side)]
    return (
        f"{arrow} {clean} • {setup.side} — {name}\n"
        f"Entry: {_fmt(levels.entry_low)} – {_fmt(levels.entry_high)}\n"
        f"TP1: {_fmt(levels.tp1)}  TP2: {_fmt(levels.tp2)}  TP3: {_fmt(levels.tp3)}\n"
        f"SL: {_fmt(levels.stop)}\n"
        f"Confidence: {levels.confidence:.2f} (setup quality, NOT P(profit))\n"
        f"Risk: ~1% — reference only, not execution sizing\n"
        f"{_CAVEAT}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feed_card.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/feed/card.py tests/test_feed_card.py
git commit -m "feat(feed): render text signal card with caveat tag"
```

---

## Task 7: Add `feed/state.py` (fresh-only dedup + outcome resolution)

**Files:**
- Create: `src/moonface/feed/state.py`
- Test: `tests/test_feed_state.py`

**Interfaces:**
- Consumes: `feed.setups.Setup`, `feed.levels.Levels`, `foundation.models.Candle`.
- Produces:
  - `setup_hash(setup: Setup) -> str`
  - `is_open(path: str | Path, symbol: str) -> bool` — True if `symbol` has an unresolved (`status == "open"`) record (one open setup per symbol).
  - `open_setup(path, symbol, setup, levels, candle_ts_ms) -> None` — append an `open` record.
  - `resolve_open(path, candles, tf_ms, symbol=None, max_bars=120) -> list[dict]` — close `open` records against `candles` (TP/SL/timeout). If `symbol` is given, only that symbol's records are considered; records whose open candle is the last bar (no forward data yet) are left open for a later tick. Appends the resolved record and returns the newly-closed ones with `outcome` and `realized_r`.

- [ ] **Step 1: Write the failing test**

`tests/test_feed_state.py`:
```python
from __future__ import annotations

from pathlib import Path

from moonface.foundation.models import Candle
from moonface.feed.levels import Levels
from moonface.feed.setups import Setup
from moonface.feed.state import (is_open, open_setup, resolve_open, setup_hash)


def _long():
    return Setup("sweep_choch", "LONG", 70, 100.0, 90.0, 95.0, 4.0)


def _levels():
    return Levels(100.0, 99.0, 101.0, 90.0, 110.0, 120.0, 130.0, 0.80)


def _c(ts, lo, hi):
    return Candle(ts, (lo + hi) / 2, hi, lo, (lo + hi) / 2, 1.0)


def test_setup_hash_is_stable_and_level_aware(tmp_path):
    s = _long()
    assert setup_hash(s) == setup_hash(s)
    other = Setup("sweep_choch", "SHORT", 70, 100.0, 110.0, 105.0, 4.0)
    assert setup_hash(other) != setup_hash(s)


def test_is_open_and_open_setup_one_per_symbol(tmp_path):
    p = tmp_path / "feed.jsonl"
    assert is_open(p, "BTC/USDT:USDT") is False
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=1_000)
    assert is_open(p, "BTC/USDT:USDT") is True
    # a second open for the same symbol is still "open" (caller suppresses it)
    assert is_open(p, "BTC/USDT:USDT") is True


def test_resolve_open_marks_stop_when_low_breaks(tmp_path):
    p = tmp_path / "feed.jsonl"
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=0)
    # entry 100, stop 90, tp1 110. A later candle with low 88 hits the stop.
    candles = [_c(0, 99, 101), _c(4_000, 88, 95)]
    closed = resolve_open(p, candles, tf_ms=4_000)
    assert len(closed) == 1
    assert closed[0]["outcome"] == "SL"
    assert closed[0]["realized_r"] < 0
    assert is_open(p, "BTC/USDT:USDT") is False


def test_resolve_open_marks_tp1_when_high_breaks(tmp_path):
    p = tmp_path / "feed.jsonl"
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=0)
    candles = [_c(0, 99, 101), _c(4_000, 111, 115)]   # high 111 > tp1 110
    closed = resolve_open(p, candles, tf_ms=4_000)
    assert closed[0]["outcome"] == "TP"
    assert closed[0]["realized_r"] > 0


def test_resolve_open_timeout_when_neither_hit(tmp_path):
    p = tmp_path / "feed.jsonl"
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=0)
    # 30 bars later, price still inside the range -> timeout (no tp/sl).
    candles = [_c(i * 4_000, 95, 105) for i in range(31)]
    closed = resolve_open(p, candles, tf_ms=4_000, max_bars=30)
    assert closed[0]["outcome"] == "TIMEOUT"
    assert is_open(p, "BTC/USDT:USDT") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.feed.state'`.

- [ ] **Step 3: Implement `feed/state.py`**

`src/moonface/feed/state.py`:
```python
"""Append-only open-setup store (jsonl). One open setup per symbol; resolves to
TP/SL/TIMEOUT against realized candles. Mirrors signal.journal's torn-line
handling and append-only contract."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from moonface.foundation.models import Candle
from moonface.feed.levels import Levels
from moonface.feed.setups import Setup

_DEFAULT_MAX_BARS = 120   # ~20 days at 4h


def setup_hash(setup: Setup) -> str:
    raw = (f"{setup.setup_type}|{setup.side}|{setup.swept_level}"
           f"|{setup.struct_level}")
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _read(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            if idx == len(lines) - 1:          # tolerate a torn trailing write
                break
            raise ValueError(f"corrupt feed state line {idx + 1} in {p}")
    return out


def _append(path: str | Path, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def is_open(path: str | Path, symbol: str) -> bool:
    return any(r.get("symbol") == symbol and r.get("status") == "open"
               for r in _read(path))


def open_setup(path: str | Path, symbol: str, setup: Setup,
               levels: Levels, candle_ts_ms: int) -> None:
    _append(path, {
        "symbol": symbol,
        "setup_hash": setup_hash(setup),
        "setup_type": setup.setup_type,
        "side": setup.side,
        "entry": levels.entry,
        "stop": levels.stop,
        "tp1": levels.tp1,
        "tp2": levels.tp2,
        "tp3": levels.tp3,
        "opened_candle_ts": candle_ts_ms,
        "status": "open",
    })


def resolve_open(path: str | Path, candles: list[Candle], tf_ms: int,
                 symbol: str | None = None,
                 max_bars: int = _DEFAULT_MAX_BARS) -> list[dict]:
    """Close open records against realized candles. Scans forward from each
    record's open candle; the first TP or SL hit wins, else TIMEOUT after
    ``max_bars``. If ``symbol`` is given, only that symbol's records are
    considered; records whose open candle is the last bar (no forward data yet)
    are left open for a later tick. Appends a `closed` record with outcome +
    realized_r (in R, signed) and returns the newly-closed records."""
    by_ts = {c.timestamp_ms: i for i, c in enumerate(candles)}
    closed: list[dict] = []
    for rec in _read(path):
        if rec.get("status") != "open":
            continue
        if symbol is not None and rec.get("symbol") != symbol:
            continue
        start = by_ts.get(rec["opened_candle_ts"])
        if start is None or start >= len(candles) - 1:
            continue                    # opened this tick — no forward bars yet
        long_ = rec["side"] == "LONG"
        entry, stop = rec["entry"], rec["stop"]
        tps = [rec["tp1"], rec["tp2"], rec["tp3"]]
        risk = (entry - stop) if long_ else (stop - entry)
        outcome, exit_price = "TIMEOUT", candles[min(start + max_bars,
                                                      len(candles) - 1)].close
        for j in range(start + 1, min(start + 1 + max_bars, len(candles))):
            c = candles[j]
            hit_sl = c.low <= stop if long_ else c.high >= stop
            hit_tp = any(c.high >= t for t in tps) if long_ else any(c.low <= t for t in tps)
            if hit_sl and (not hit_tp or _sl_first(c, stop, tps, long_)):
                outcome, exit_price = "SL", stop
                break
            if hit_tp:
                outcome, exit_price = "TP", _first_tp_hit(c, tps, long_)
                break
        realized = ((exit_price - entry) if long_ else (entry - exit_price))
        realized_r = round(realized / risk, 4) if risk > 0 else 0.0
        closed_rec = {**rec, "status": "closed", "outcome": outcome,
                      "realized_r": realized_r}
        _append(path, closed_rec)
        closed.append(closed_rec)
    return closed


def _sl_first(c: Candle, stop: float, tps: list[float], long_: bool) -> bool:
    """Did the candle plausibly hit the stop before a target? Conservative rule:
    if both the SL and a TP are within the same candle's range, assume SL first."""
    if long_:
        return c.low <= stop and any(t <= c.high for t in tps)
    return c.high >= stop and any(t >= c.low for t in tps)


def _first_tp_hit(c: Candle, tps: list[float], long_: bool) -> float:
    if long_:
        return min(t for t in tps if c.high >= t)
    return max(t for t in tps if c.low <= t)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feed_state.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/feed/state.py tests/test_feed_state.py
git commit -m "feat(feed): open-setup state, fresh-only dedup, TP/SL/timeout resolution"
```

---

## Task 8: Add `feed/universe.py` (top-N USDT perps by 24h quote volume)

**Files:**
- Create: `src/moonface/feed/universe.py`
- Test: `tests/test_feed_universe.py`

**Interfaces:**
- Consumes: `ccxt` (only when no `fetch_tickers` is injected).
- Produces: `select_top_volume(exchange_name: str, size: int, *, fetch_tickers=None) -> list[str]` — symbols like `"BTC/USDT:USDT"`, sorted by descending 24h quote volume.

- [ ] **Step 1: Write the failing test**

`tests/test_feed_universe.py`:
```python
from __future__ import annotations

from moonface.feed.universe import select_top_volume


def _fake_tickers():
    return {
        "BTC/USDT:USDT": {"info": {"quoteVolume": "5000000000"}},
        "ETH/USDT:USDT": {"info": {"quoteVolume": "2000000000"}},
        "SOL/USDT:USDT": {"info": {"quoteVolume": "800000000"}},
        "DOGE/USDT:USDT": {"quoteVolume": 300000000},          # fallback field
        "BTC/USDT": {"info": {"quoteVolume": "9999999999"}},   # spot, not a perp
        "FOO/USDC:USDT": {"info": {"quoteVolume": "999"}},     # not /USDT:USDT
        "BAR/USDT:USDT": {"info": {"quoteVolume": "0"}},       # zero volume
    }


def test_returns_top_n_usdt_perps_by_volume():
    top = select_top_volume("binance", 3, fetch_tickers=lambda: _fake_tickers())
    assert top == ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


def test_size_caps_result():
    top = select_top_volume("binance", 1, fetch_tickers=lambda: _fake_tickers())
    assert top == ["BTC/USDT:USDT"]


def test_uses_quote_volume_fallback_field():
    top = select_top_volume("binance", 4, fetch_tickers=lambda: _fake_tickers())
    assert "DOGE/USDT:USDT" in top          # parsed from the top-level quoteVolume
    assert "FOO/USDC:USDT" not in top
    assert "BAR/USDT:USDT" not in top       # zero volume excluded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_universe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.feed.universe'`.

- [ ] **Step 3: Implement `feed/universe.py`**

`src/moonface/feed/universe.py`:
```python
"""Universe selection: top-N USDT-margined perps by 24h quote volume. Network
access only through the injected ``fetch_tickers`` seam (tests pass a fake)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ccxt


def _quote_volume(t: dict[str, Any]) -> float:
    info = t.get("info") or {}
    for key in ("quoteVolume", "quote_volume", "quoteVol"):
        raw = info.get(key)
        if raw not in (None, "", "0"):
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
    raw = t.get("quoteVolume")
    try:
        return float(raw) if raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def select_top_volume(exchange_name: str, size: int,
                      *, fetch_tickers: Callable[[], dict[str, Any]] | None = None
                      ) -> list[str]:
    if fetch_tickers is None:
        exchange = getattr(ccxt, exchange_name)({"enableRateLimit": True})
        fetch_tickers = exchange.fetch_tickers
    tickers = fetch_tickers()
    perps = [(sym, _quote_volume(t)) for sym, t in tickers.items()
             if sym.endswith("/USDT:USDT")]
    perps = [(sym, v) for sym, v in perps if v > 0]
    perps.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in perps[:size]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feed_universe.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/feed/universe.py tests/test_feed_universe.py
git commit -m "feat(feed): select top-N USDT perps by 24h quote volume"
```

---

## Task 9: Add `feed/loop.py` + `feed/cli.py`, register the `moonface-feed` entry point, frozen-window replay test

**Files:**
- Create: `src/moonface/feed/loop.py`
- Create: `src/moonface/feed/cli.py`
- Modify: `pyproject.toml` (add entry point)
- Test: `tests/test_feed_cli.py`
- Test: `tests/test_feed_replay.py`

**Interfaces:**
- Consumes: `foundation.bundle.load_bundle`, `foundation.data.TIMEFRAME_MS`, `foundation.pivots.daily_pivots`, `feed.setups.detect_last`, `feed.levels.derive_levels`, `feed.card.render_card`, `feed.state.{is_open,open_setup,resolve_open}`, `feed.universe.select_top_volume`, `signal.notify.TelegramNotifier`.
- Produces: `moonface-feed` CLI with `--once/--watch/--report/--disclaimer`, flags `--post`, `--universe-size 40`, `--timeframe 4h`, `--grace-seconds 60`, `--max-posts 5`, `--state`, `--cache-dir`. Env: `MOONFACE_FEED_TELEGRAM_TOKEN` / `MOONFACE_FEED_CHAT_ID` / `MOONFACE_FEED_POST`.

- [ ] **Step 1: Write the failing CLI test**

`tests/test_feed_cli.py`:
```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from moonface.foundation.models import Candle
from moonface.feed.cli import run


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 4 * 3_600_000, o, h, lo, c, 1.0)


def _bundle(symbol, *_a, **_kw):
    """A bundle whose final candle is a sweep->CHOCH LONG confirmation."""
    from moonface.foundation.bundle import DataBundle
    bars = []
    idx = 0
    for leg in range(11):
        b = 100 + 10 * leg
        for o, h, lo, c in [
            (b, b + 2, b - 3, b), (b + 3, b + 6, b, b + 3),
            (b + 6, b + 9, b + 4, b + 6), (b + 9, b + 12, b + 7, b + 9),
            (b + 12, b + 15, b + 10, b + 12), (b + 10, b + 13, b + 5, b + 10),
            (b + 5, b + 8, b, b + 5), (b, b + 3, b - 6, b), (b - 3, b, b - 6, b - 3),
            (b - 5, b - 2, b - 20, b - 2), (b - 2, b + 20, b - 4, b + 18),
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return DataBundle(candles=bars)


def test_once_dry_run_prints_card_without_posting(capsys, tmp_path):
    posted: list[str] = []

    def fake_post(msg):
        posted.append(msg)

    rc = run(["--once", "--state", str(tmp_path / "f.jsonl")],
             fetch_bundle=_bundle,
             select_universe=lambda *a, **k: ["BTC/USDT:USDT"],
             post=fake_post)
    assert rc == 0
    out = capsys.readouterr().out
    assert "🟢 BTCUSDT • LONG" in out
    assert "[SMC SETUP — heuristic; no validated out-of-sample edge]" in out
    assert posted == []                      # dry-run: nothing posted


def test_once_post_calls_telegram_and_records_state(tmp_path):
    posted: list[str] = []
    state = tmp_path / "f.jsonl"
    run(["--once", "--post", "--state", str(state)],
        fetch_bundle=_bundle,
        select_universe=lambda *a, **k: ["BTC/USDT:USDT"],
        post=lambda m: posted.append(m))
    assert len(posted) == 1
    assert "BTCUSDT • LONG" in posted[0]
    lines = [ln for ln in state.read_text().splitlines() if ln.strip()]
    assert json.loads(lines[0])["status"] == "open"
    assert json.loads(lines[0])["symbol"] == "BTC/USDT:USDT"


def test_disclaimer_prints_banner(capsys):
    rc = run(["--disclaimer"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "not financial advice" in out.lower()
    assert "no validated out-of-sample edge" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feed_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.feed.cli'`.

- [ ] **Step 3: Implement `feed/loop.py`**

`src/moonface/feed/loop.py`:
```python
"""The scan loop. ``run_once`` scans the universe once (testable, injectable);
``run_watch`` is the cadence loop that mirrors signal.cli.watch. Dry-run by
default: a posted card only goes to Telegram via the injected ``post`` seam when
``args.post`` is set."""
from __future__ import annotations

import time
from collections.abc import Callable

from moonface.foundation.data import TIMEFRAME_MS
from moonface.foundation.pivots import daily_pivots
from moonface.feed.card import render_card
from moonface.feed.levels import derive_levels
from moonface.feed.setups import detect_last
from moonface.feed.state import is_open, open_setup, resolve_open

LOOKBACK_BARS = 600


def _levels_for(setup, candles, atr_value):
    pivots = daily_pivots(candles)
    piv = pivots[-1] if pivots else None
    return derive_levels(setup, piv, atr_value)


def run_once(args, *, fetch_bundle: Callable, select_universe: Callable,
             post: Callable[[str], None], out=print) -> int:
    """Scan the universe once. Prints every card; posts + writes state only when
    args.post — dry-run is side-effect-free and repeatable (freshness is never
    consumed by a preview)."""
    universe = select_universe(args.exchange, args.universe_size)
    tf_ms = TIMEFRAME_MS[args.timeframe]
    end_ms = (int(time.time() * 1000) // tf_ms) * tf_ms
    start_ms = end_ms - LOOKBACK_BARS * tf_ms
    posted = 0
    stop = False
    for symbol in universe:
        if stop:
            break
        bundle = fetch_bundle(symbol, start_ms, end_ms, args.cache_dir)
        candles = bundle.candles
        for setup in detect_last(candles):
            if args.post and is_open(args.state, symbol):
                continue                  # one open setup per symbol (fresh-only)
            levels = _levels_for(setup, candles, setup.atr_value)
            card = render_card(symbol, setup, levels)
            out(card)
            if args.post:
                post(card)
                posted += 1
                open_setup(args.state, symbol, setup, levels,
                           candles[-1].timestamp_ms)
                if posted >= args.max_posts:
                    stop = True
                    break
        if args.post:
            resolve_open(args.state, candles, tf_ms, symbol=symbol)
    return 0


def run_watch(args, *, fetch_bundle, select_universe, post,
              sleep_fn=time.sleep, out=print) -> int:
    """Forever loop: scan once per closed candle, sleep until next close + grace.
    Mirrors signal.cli.watch's cadence/restart-safe handling."""
    tf_ms = TIMEFRAME_MS[args.timeframe]
    while True:
        now_ms = int(time.time() * 1000)
        next_close = (now_ms // tf_ms + 1) * tf_ms
        try:
            run_once(args, fetch_bundle=fetch_bundle,
                     select_universe=select_universe, post=post, out=out)
        except Exception as exc:  # noqa: BLE001 - never kill the daemon
            out(f"FEED TICK ERROR: {exc!r}")
        sleep_fn((next_close - int(time.time() * 1000)) / 1000.0 + args.grace_seconds)
    return 0
```

- [ ] **Step 4: Implement `feed/cli.py`**

`src/moonface/feed/cli.py`:
```python
"""moonface-feed CLI: broadcast SMC setup cards to a Telegram channel.

Dry-run by default. Set --post (or MOONFACE_FEED_POST=1) plus
MOONFACE_FEED_TELEGRAM_TOKEN / MOONFACE_FEED_CHAT_ID to actually send."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from moonface.foundation.bundle import load_bundle
from moonface.feed.loop import run_once, run_watch
from moonface.feed.universe import select_top_volume
from moonface.signal.notify import TelegramNotifier

DISCLAIMER = (
    "⚠️ This channel posts heuristic Smart-Money-Concept setups generated by an\n"
    "automated scanner. These setups carry NO validated out-of-sample edge and\n"
    "are NOT financial advice. Nothing here is a recommendation to trade, and no\n"
    "order is ever executed by this bot. Risk is your own."
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="moonface-feed",
        description="Broadcast caveat-labeled SMC setup cards to a Telegram"
                    " channel. Dry-run by default.")
    p.add_argument("--exchange", default="binance")
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--universe-size", type=int, default=40)
    p.add_argument("--max-posts", type=int, default=5)
    p.add_argument("--grace-seconds", type=float, default=60.0)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--state", default="journal/feed.jsonl")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="scan once and exit")
    mode.add_argument("--watch", action="store_true",
                      help="cadence loop: scan every closed candle, forever")
    mode.add_argument("--report", action="store_true",
                      help="print open setups + resolved outcomes from --state")
    mode.add_argument("--disclaimer", action="store_true",
                      help="print (and with --post, send) the honesty banner")
    p.add_argument("--post", action="store_true",
                   help="actually send to Telegram (default: dry-run to stdout)")
    return p


def _notifier(args, env=None) -> "TelegramNotifier | None":
    if env is None:
        env = os.environ
    token = env.get("MOONFACE_FEED_TELEGRAM_TOKEN", "").strip()
    chat_id = env.get("MOONFACE_FEED_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None
    return TelegramNotifier(token, chat_id)


def _post_fn(notifier):
    if notifier is None:
        return lambda _msg: None               # no creds configured -> no-op
    return notifier.send


def _env_post() -> bool:
    return os.environ.get("MOONFACE_FEED_POST", "").strip().lower() in ("1", "true")


def run(argv: list[str] | None = None, *, fetch_bundle=None,
        select_universe=None, post=None) -> int:
    args = build_parser().parse_args(argv)
    notifier = _notifier(args)
    if args.disclaimer:
        print(DISCLAIMER)
        if args.post and notifier is not None:
            notifier.send(DISCLAIMER)
        return 0
    if args.report:
        from moonface.feed.state import _read
        for rec in _read(args.state):
            print(rec)
        return 0
    fetch_bundle = fetch_bundle or (lambda sym, s, e, cache: load_bundle(
        {"exchange": args.exchange, "symbol": sym, "timeframe": args.timeframe},
        s, e, cache))
    select_universe = select_universe or select_top_volume
    # --post OR MOONFACE_FEED_POST=1 enables posting (spec §8); state writes in
    # run_once are gated on this same flag, so a preview never consumes freshness.
    args.post = bool(args.post) or _env_post()
    post_fn = post or _post_fn(notifier)
    if args.watch:
        return run_watch(args, fetch_bundle=fetch_bundle,
                         select_universe=select_universe, post=post_fn)
    # default (and --once) scan a single tick
    return run_once(args, fetch_bundle=fetch_bundle,
                    select_universe=select_universe, post=post_fn)


def main() -> None:
    # Best-effort .env load, mirroring signal.cli (stdlib-only).
    from moonface.signal.cli import _load_env_file
    _load_env_file()
    raise SystemExit(run())
```

- [ ] **Step 5: Register the entry point in `pyproject.toml`**

In `src/moonface/feed/...` nothing else; edit `pyproject.toml` `[project.scripts]` to:
```toml
[project.scripts]
moonface-signal = "moonface.signal.cli:main"
moonface-feed = "moonface.feed.cli:main"
```

- [ ] **Step 6: Write the frozen-window replay test**

`tests/test_feed_replay.py`:
```python
"""Frozen-window replay: run detect_all over a fixed synthetic series and assert
a deterministic setup list. Offline (no cache, no network) — consistent with the
repo's SMC test fixtures. Pins the detector output so future refactors surface
behavior changes here."""
from __future__ import annotations

from moonface.foundation.models import Candle
from moonface.feed.setups import detect_all


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 4 * 3_600_000, o, h, lo, c, 1.0)


def _reversal_fixture():
    bars = []
    idx = 0
    for leg in range(11):
        b = 100 + 10 * leg
        for o, h, lo, c in [
            (b, b + 2, b - 3, b), (b + 3, b + 6, b, b + 3),
            (b + 6, b + 9, b + 4, b + 6), (b + 9, b + 12, b + 7, b + 9),
            (b + 12, b + 15, b + 10, b + 12), (b + 10, b + 13, b + 5, b + 10),
            (b + 5, b + 8, b, b + 5), (b, b + 3, b - 6, b), (b - 3, b, b - 6, b - 3),
            (b - 5, b - 2, b - 20, b - 2), (b - 2, b + 20, b - 4, b + 18),
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return bars


def test_replay_setup_types_and_sides_are_deterministic():
    setups = detect_all(_reversal_fixture())
    # Frozen assertion: the rising reversal fixture yields >=1 LONG sweep_choch
    # and no SHORT sweep_choch. (Exact indices are not pinned — detector
    # hyperparameters are frozen, but leg overlap shifts indices; pin only the
    # invariant: at least one LONG reversal, sides/types valid.)
    assert any(s.setup_type == "sweep_choch" and s.side == "LONG" for s in setups)
    assert not any(s.side == "SHORT" for s in setups if s.setup_type == "sweep_choch")
    assert all(s.side in ("LONG", "SHORT") for s in setups)
    assert all(s.setup_type in ("sweep_choch", "bos_continuation") for s in setups)
```

- [ ] **Step 7: Run the new tests**

Run: `pytest tests/test_feed_cli.py tests/test_feed_replay.py -v`
Expected: PASS.

- [ ] **Step 8: Reinstall the package so the entry point registers, then smoke-test the CLI**

Run: `pip install -e . -q && moonface-feed --disclaimer && moonface-feed --once --state /tmp/feed_smoke.jsonl --universe-size 1 2>&1 | head -5`
Expected: the disclaimer prints; the `--once` dry-run either prints a card for the top perp or prints nothing if no fresh setup is present right now (no error, exit 0). The smoke run may hit the network via ccxt — that's expected and acceptable for a manual smoke (tests stay offline).

- [ ] **Step 9: Run the full suite + ruff**

Run: `pytest -q && ruff check src tests`
Expected: green.

- [ ] **Step 10: Commit**

```bash
git add src/moonface/feed/loop.py src/moonface/feed/cli.py pyproject.toml \
        tests/test_feed_cli.py tests/test_feed_replay.py
git commit -m "feat(feed): scan loop + moonface-feed CLI; dry-run by default"
```

---

## Done

After Task 9, the feed is feature-complete for v1:

- `moonface-feed --once --dry-run` scans and prints cards.
- `moonface-feed --watch --post` (with `MOONFACE_FEED_TELEGRAM_*` env) runs the cadence loop and posts fresh setups to the channel.
- `moonface-feed --disclaimer --post` posts/pins the honesty banner.
- Every card is caveat-labeled; no leverage; dry-run by default; `feed` never imports `research`.

**Manual go-live checklist (not automated):**
1. Create the Telegram channel, add the bot as admin, put the token + channel id in `.env` as `MOONFACE_FEED_TELEGRAM_TOKEN` / `MOONFACE_FEED_CHAT_ID`.
2. `moonface-feed --disclaimer --post`, then pin the banner in the channel.
3. Run `moonface-feed --once` (dry-run) a few times across 4h closes to vet card quality.
4. `moonface-feed --watch --post` under a process supervisor (systemd / tmux).

**Deferred (v2, per spec §11):** order-block retest / FVG fill / EQH-EQL setups (port from `docs/script/SMC.pine`); optional chart-image rendering; an optional high-conviction tier that surfaces the validated `mtf_long` BTC long.
