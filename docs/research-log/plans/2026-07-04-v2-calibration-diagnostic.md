# Confluence Engine v2 Score-Calibration Diagnostic — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only offline diagnostic that answers one pre-registered question — does the frozen v2 confluence score order trade outcomes on history? — without touching the frozen engine, its constants, or the running forward-paper record.

**Architecture:** One new pure module `src/moonface/signal/engine/calibration.py` (scoring pass replicating `evaluate_engine`'s frozen call sequence; hypothetical-trade simulator reusing the frozen `open_position`/`manage_position`; stdlib statistics: Spearman, moving-block bootstrap, Newey–West) plus one thin CLI `tools/engine_calibration.py`. Results land in a pre-frozen report doc `experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md`.

**Tech Stack:** Python 3.11+, stdlib only (no numpy). pytest (plain test functions, repo style). ruff.

## Global Constraints

- **Spec:** `docs/research-log/specs/2026-07-04-v2-calibration-diagnostic-design.md`. Read it before starting any task.
- **NEVER edit any existing file under `src/moonface/signal/engine/` or `tools/`.** This lane only CREATES files. If a task seems to need an edit to frozen code, STOP and report — that is a spec violation.
- The frozen registration hash must remain exactly `10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf` (`engine_hash(EngineConfig())`). Task 1 pins this in a test.
- Python: run everything as `.venv/bin/python -m pytest ...` / `.venv/bin/python -m tools....` — there is NO bare `python` on PATH and the rtk hook does not proxy `python`.
- Tests: plain pytest functions (see `tests/test_engine_position.py` for house style). Deterministic randomness only, via `random.Random(seed)`.
- Ruff must stay clean: `.venv/bin/python -m ruff check src tools tests`.
- Git: NEVER chain `git add && git commit` in one command. Stage, then verify with `git diff --cached --stat`, then commit. No AI-attribution trailers in commit messages. Do not push.
- Project CLAUDE.md asks for `gitnexus_detect_changes()` before commits; this lane only adds new files, so expect additions only. If the tool is unavailable to you, note that in the task report and proceed.
- Frozen analysis constants (from the spec, echoed in code in Task 1): block length 168 bars, bootstrap draws 1000, seed 20260704, IC horizon 24 bars, NW lag 24, bucket edges 40/60/75, panel floor 200, ≥60-bucket floor 30.

---

### Task 1: Scoring pass — `BarRow`, `scoring_pass`, parity + hash-invariance tests

**Files:**
- Create: `src/moonface/signal/engine/calibration.py`
- Test: `tests/test_engine_calibration_pass.py`

**Interfaces:**
- Consumes (all frozen, read-only):
  - `moonface.signal.engine.config.EngineConfig`, `engine_hash(cfg) -> str`
  - `moonface.signal.engine.confluence.decide(trend_scores, revert_scores, macro, cfg) -> Decision`; constants `GATE`, `BASE_THRESHOLD`, `CT_SURCHARGE`, `BREADTH_MIN`
  - `moonface.signal.engine.macro.classify_macro(weekly, vol_state, cfg) -> MacroState`
  - `moonface.signal.engine.regime.classify_regime(candles_4h, cfg) -> Regime`
  - `moonface.signal.engine.modules.trend_book.build_views(candles_1h) -> TfViews`, `trend_book.score(views, macro, deriv, cfg) -> list[ModuleScore]`
  - `moonface.signal.engine.modules.revert_book.score(...) -> list[ModuleScore]`, `revert_book.sweep_state(h1) -> SweepState | None`
- Produces (later tasks rely on these exact names):
  - `BookState(direction: int, score: int, breadth: int, policy: str | None)` frozen dataclass
  - `BarRow(index: int, ts_ms: int, macro_effective: str, vol_state: str, regime_trend: int, trend: BookState, revert: BookState, module_points: dict[str, int], sweep_wick: float | None, decision_action: str, decision_direction: int, decision_score: int)` frozen dataclass
  - `scoring_pass(cfg: EngineConfig, candles: list[Candle], warmup: int) -> list[BarRow]`
  - Module constants: `BLOCK_BARS=168`, `BOOTSTRAP_DRAWS=1000`, `BOOTSTRAP_SEED=20260704`, `IC_HORIZON_BARS=24`, `NW_LAG=24`, `BUCKET_EDGES=(40, 60, 75)`, `PANEL_FLOOR=200`, `TRIGGER_BUCKET_FLOOR=30`, `_TREND_MODULES`, `_REVERT_MODULES`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_calibration_pass.py
"""Scoring pass of the read-only v2 calibration diagnostic.

Parity claim (spec §2c): the pass calls the SAME frozen functions
evaluate_engine calls, in the same order, on the same rolling window — so its
Decision must equal evaluate_engine's Decision bar-for-bar while flat."""
import random

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from moonface.signal.engine.calibration import BarRow, BookState, scoring_pass
from moonface.signal.engine.config import EngineConfig, engine_hash
from moonface.signal.engine.engine import evaluate_engine

H = 3_600_000

FROZEN_HASH = "10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf"


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


def _cfg(**kw):
    base = dict(lookback_bars=400)
    base.update(kw)
    return EngineConfig(**base)


def test_engine_hash_is_the_frozen_registration_hash():
    # Defense-in-depth for the whole lane: importing calibration code must not
    # perturb the frozen identity. calibration is imported at module top.
    assert engine_hash(EngineConfig()) == FROZEN_HASH


def test_scoring_pass_row_shape_and_indices():
    candles = _walk_series(420)
    rows = scoring_pass(_cfg(), candles, warmup=380)
    assert len(rows) == 420 - 380
    first = rows[0]
    assert isinstance(first, BarRow)
    assert first.index == 380
    assert first.ts_ms == candles[380].timestamp_ms
    assert isinstance(first.trend, BookState)
    assert isinstance(first.revert, BookState)
    # all 12 module names present in the signed-points map
    assert len(first.module_points) == 12
    assert "m1_macro" in first.module_points
    assert "m6_stretch" in first.module_points


def test_scoring_pass_decision_parity_with_evaluate_engine():
    candles = _walk_series(430, seed=11)
    cfg = _cfg()
    warmup = 380
    rows = scoring_pass(cfg, candles, warmup)
    window = cfg.lookback_bars
    for row in rows:
        j = row.index
        lo = max(0, j + 1 - window)
        sub = DataBundle(candles=candles[lo:j + 1])
        res = evaluate_engine(cfg, sub, entries=[],
                              now_ms=candles[j].timestamp_ms)
        assert res.decision is not None
        assert row.decision_action == res.decision.action
        assert row.decision_direction == res.decision.direction
        assert row.decision_score == res.decision.score
        assert row.vol_state == res.regime_vol
        assert row.regime_trend == res.regime_trend


def test_book_state_policy_only_when_directional():
    candles = _walk_series(420, seed=3)
    rows = scoring_pass(_cfg(), candles, warmup=380)
    for row in rows:
        for state in (row.trend, row.revert):
            if state.direction == 0:
                assert state.policy is None
            else:
                assert state.policy in ("ALLOW", "ALLOW_CT", "REJECT")


def test_sweep_wick_only_when_revert_directional():
    candles = _walk_series(420, seed=5)
    rows = scoring_pass(_cfg(), candles, warmup=380)
    for row in rows:
        if row.sweep_wick is not None:
            assert row.revert.direction != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.calibration'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/calibration.py
"""Read-only score-calibration diagnostic for the frozen v2 engine.

Answers ONE pre-registered question from historical replay: does the v2
confluence score order trade outcomes? DIAGNOSTIC ONLY — this module never
gates, never mutates state, never recommends a constant change, and touches
no frozen value (spec docs/research-log/specs/
2026-07-04-v2-calibration-diagnostic-design.md).

Forward parity is at the FUNCTION level: the scoring pass calls the same
frozen functions evaluate_engine calls, in the same order, over the same
rolling lookback window; the simulator reuses the frozen open_position /
manage_position exit discipline verbatim."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from moonface.foundation.models import Candle
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.confluence import GATE, decide
from moonface.signal.engine.macro import classify_macro
from moonface.signal.engine.modules import revert_book, trend_book
from moonface.signal.engine.regime import classify_regime

# Frozen ANALYSIS constants (spec §4) — diagnostic-only, deliberately NOT part
# of engine_hash: they parameterize the measurement, not the engine.
BLOCK_BARS = 168            # 7d of 1h bars — moving-block bootstrap block
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 20260704
IC_HORIZON_BARS = 24        # secondary module-IC forward-return horizon
NW_LAG = 24
BUCKET_EDGES = (40, 60, 75)  # buckets: <40, 40-59, 60-74, >=75
PANEL_FLOOR = 200           # power floor: min panel events per book
TRIGGER_BUCKET_FLOOR = 30   # power floor: min events with score >= 60

_TREND_MODULES = ("m1_macro", "m2_breakout", "m2_ma_align", "m3_roc",
                  "m4_pullback", "m5_funding")
_REVERT_MODULES = ("m1_sweep", "m2_reclaim", "m3_divergence", "m4_fund_ct",
                   "m5_oi_flush", "m6_stretch")
_BOOK_LABEL = {"trend": "TREND", "mean_revert": "MEAN_REVERT"}
_DIR_LABEL = {1: "LONG", -1: "SHORT"}

DIAGNOSTIC_LABEL = ("calibration diagnostic — read-only, no edge claim, "
                    "no constant recommendation")


@dataclass(frozen=True)
class BookState:
    direction: int
    score: int
    breadth: int
    policy: str | None


@dataclass(frozen=True)
class BarRow:
    index: int
    ts_ms: int
    macro_effective: str
    vol_state: str
    regime_trend: int
    trend: BookState
    revert: BookState
    module_points: dict[str, int]
    sweep_wick: float | None
    decision_action: str
    decision_direction: int
    decision_score: int


def _book_state(book_scores, archetype: str, macro_effective: str) -> BookState:
    # Mirrors confluence._book_context's signed-sum/direction/breadth exactly.
    signed = sum(m.direction * m.points for m in book_scores)
    direction = 1 if signed > 0 else (-1 if signed < 0 else 0)
    score = abs(signed)
    breadth = sum(1 for m in book_scores
                  if m.direction == direction and m.points > 0)
    policy = None
    if direction != 0:
        policy = GATE[(macro_effective, _BOOK_LABEL[archetype],
                       _DIR_LABEL[direction])]
    return BookState(direction, score, breadth, policy)


def scoring_pass(cfg: EngineConfig, candles: list[Candle],
                 warmup: int) -> list[BarRow]:
    """Per closed bar, the frozen scoring sequence evaluate_engine runs
    (build_views -> classify_regime -> classify_macro -> book scores ->
    decide) over the same rolling lookback_bars window, deriv=None."""
    window = cfg.lookback_bars
    rows: list[BarRow] = []
    for j in range(warmup, len(candles)):
        lo = max(0, j + 1 - window)
        sub = candles[lo:j + 1]
        views = trend_book.build_views(sub)
        regime = classify_regime(views.h4, cfg)
        macro = classify_macro(views.w1, regime.vol_state, cfg)
        trend_scores = trend_book.score(views, macro, None, cfg)
        revert_scores = revert_book.score(views, macro, None, cfg)
        decision = decide(trend_scores, revert_scores, macro, cfg)
        macro_eff = macro.effective()
        t_state = _book_state(trend_scores, "trend", macro_eff)
        r_state = _book_state(revert_scores, "mean_revert", macro_eff)
        module_points = {m.module: m.direction * m.points
                         for m in list(trend_scores) + list(revert_scores)}
        sweep_wick = None
        if r_state.direction != 0:
            sw = revert_book.sweep_state(views.h1)
            if sw is not None and sw.direction == r_state.direction:
                sweep_wick = sw.wick_extreme
        rows.append(BarRow(
            index=j, ts_ms=candles[j].timestamp_ms,
            macro_effective=macro_eff, vol_state=regime.vol_state,
            regime_trend=regime.trend, trend=t_state, revert=r_state,
            module_points=module_points, sweep_wick=sweep_wick,
            decision_action=decision.action,
            decision_direction=decision.direction,
            decision_score=decision.score))
    return rows


def series_fingerprint(candles: list[Candle]) -> str:
    h = hashlib.sha256()
    for c in candles:
        h.update(f"{c.timestamp_ms},{c.close}\n".encode())
    return h.hexdigest()
```

Task 1's import block contains only what Task 1 uses (ruff-clean as committed).
Tasks 2–4 each add their own imports alongside their code — the exact additions
are spelled out in each task's Step 3.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py -v`
Expected: 5 passed

- [ ] **Step 5: Ruff**

Run: `.venv/bin/python -m ruff check src/moonface/signal/engine/calibration.py tests/test_engine_calibration_pass.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/calibration.py tests/test_engine_calibration_pass.py
git diff --cached --stat   # verify exactly these 2 files
git commit -m "feat(engine): calibration scoring pass with frozen-path parity (read-only diagnostic)"
```

---

### Task 2: Hypothetical-trade simulator — panels, streams, reversal sensitivity

**Files:**
- Modify: `src/moonface/signal/engine/calibration.py` (append; created in Task 1 — the ONLY file this lane ever appends to)
- Test: `tests/test_engine_calibration_sim.py`

**Interfaces:**
- Consumes: `BarRow`, `BookState`, `scoring_pass` (Task 1); frozen `open_position(candles, cfg, direction, confidence, fraction, profile, sweep_wick) -> StepResult`, `manage_position(candles, cfg, pos, signal_direction, confidence) -> StepResult`, `PositionState`
- Produces:
  - `HypoTrade(entry_index: int, exit_index: int, entry_ts_ms: int, exit_ts_ms: int, book: str, direction: int, score: int, breadth: int, policy: str | None, macro_effective: str, vol_state: str, net_r: float, bars_held: int, exit_reason: str)` frozen dataclass
  - `simulate_entry(candles, cfg, row, book, rows_by_index=None) -> HypoTrade | None` (None = data ended before exit)
  - `overlapping_panel(candles, cfg, rows, book) -> tuple[list[HypoTrade], dict]` (dict: `events`, `incomplete`, `skipped_extreme_vol`)
  - `nonoverlapping_stream(candles, cfg, rows, book) -> list[HypoTrade]`
  - `reversal_sensitivity(candles, cfg, rows, book) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_calibration_sim.py
"""Hypothetical-trade simulator: frozen exit discipline, hand-computed.

Cost model check (frozen position._net_r): net_r = gross_r - COST_FRACTION/atr_frac,
COST_FRACTION = 0.001."""
from moonface.foundation.models import Candle
from moonface.signal.engine.calibration import (BarRow, BookState,
                                                nonoverlapping_stream,
                                                overlapping_panel,
                                                reversal_sensitivity,
                                                simulate_entry)
from moonface.signal.engine.config import EngineConfig

H = 3_600_000


def _bar(i, o, hi, lo, c):
    return Candle(i * H, o, hi, lo, c, 1.0)


def _flat(n, price=100.0, spread=2.0, start=0):
    # every bar: TR = high-low = 2*spread -> ATR = 2*spread
    return [_bar(start + i, price, price + spread, price - spread, price)
            for i in range(n)]


def _cfg(**kw):
    base = dict(atr_period=3, k_stop=2.0, k_trail=3.0, max_bars=96,
                lookback_bars=400)
    base.update(kw)
    return EngineConfig(**base)


def _row(index, book, direction, score, breadth=3, policy="ALLOW",
         vol_state="normal", sweep_wick=None, decision_action="WAIT",
         decision_direction=0):
    trend = BookState(direction if book == "trend" else 0,
                      score if book == "trend" else 0,
                      breadth if book == "trend" else 0,
                      policy if book == "trend" else None)
    revert = BookState(direction if book == "mean_revert" else 0,
                       score if book == "mean_revert" else 0,
                       breadth if book == "mean_revert" else 0,
                       policy if book == "mean_revert" else None)
    return BarRow(index=index, ts_ms=index * H, macro_effective="NEUTRAL",
                  vol_state=vol_state, regime_trend=0, trend=trend,
                  revert=revert, module_points={}, sweep_wick=sweep_wick,
                  decision_action=decision_action,
                  decision_direction=decision_direction, decision_score=score)


def test_wt_long_stop_hit_hand_computed():
    # flat 100/spread 2 -> ATR 4; entry close 100, stop 100-2*4=92.
    # bar 11 low 80 <= 92 -> exit at 92: gross (92-100)/4 = -2.0,
    # cost 0.001/(4/100) = 0.025 -> net -2.025.
    candles = _flat(11)
    candles.append(_bar(11, 100, 101, 80, 85))
    t = simulate_entry(candles, _cfg(), _row(10, "trend", 1, 65), "trend")
    assert t is not None
    assert t.exit_index == 11
    assert t.net_r == -2.025
    assert "stop" in t.exit_reason


def test_ct_long_target_hit_hand_computed():
    # CT (mean_revert book): ATR 4, no sweep wick -> stop 100-1.5*4=94,
    # target 100+2*4=108. bar 11: low 99 (no stop), high 109 -> exit 108:
    # gross (108-100)/4 = 2.0, cost 0.025 -> net 1.975.
    candles = _flat(11)
    candles.append(_bar(11, 100, 109, 99, 105))
    t = simulate_entry(candles, _cfg(), _row(10, "mean_revert", 1, 70),
                       "mean_revert")
    assert t is not None
    assert t.net_r == 1.975
    assert "target" in t.exit_reason


def test_ct_sweep_wick_sets_stop_beyond_wick():
    # sweep_wick 95 -> stop 95 - 1.5*4 = 89. bar 11 low 90 does NOT stop
    # (90 > 89); bar 12 low 88 does -> exit 89: gross (89-100)/4 = -2.75,
    # net -2.775.
    candles = _flat(11)
    candles.append(_bar(11, 100, 100, 90, 95))
    candles.append(_bar(12, 95, 96, 88, 90))
    t = simulate_entry(candles, _cfg(),
                       _row(10, "mean_revert", 1, 70, sweep_wick=95.0),
                       "mean_revert")
    assert t is not None
    assert t.exit_index == 12
    assert t.net_r == -2.775


def test_incomplete_trade_returns_none():
    candles = _flat(11)  # no bars after entry at index 10
    t = simulate_entry(candles, _cfg(), _row(10, "trend", 1, 65), "trend")
    assert t is None


def test_overlapping_panel_counts_and_skips_extreme_vol():
    candles = _flat(30)
    candles.append(_bar(30, 100, 101, 80, 85))  # exit bar for all entries
    rows = [_row(10, "trend", 1, 65),
            _row(11, "trend", 1, 40, vol_state="extreme"),
            _row(12, "trend", 0, 0),          # no direction -> not an event
            _row(13, "trend", 1, 80)]
    trades, counts = overlapping_panel(candles, _cfg(), rows, "trend")
    assert counts == {"events": 2, "incomplete": 0, "skipped_extreme_vol": 1}
    assert [t.entry_index for t in trades] == [10, 13]


def test_nonoverlapping_stream_skips_while_open():
    # trade 1: entry at 10 (ATR 4, stop 92); stop-hit bar 15 (low 80). rows at
    # 11..15 must be skipped. trade 2: entry at 16 — its ATR window includes
    # bar 15's 21-point true range, so ATR=(4+21+17)/3=14 and stop=100-28=72;
    # bar 21 low 60 <= 72 exits it. row 17 is skipped while trade 2 is open.
    candles = _flat(15)
    candles.append(_bar(15, 100, 101, 80, 85))
    candles.extend(_flat(5, start=16))
    candles.append(_bar(21, 100, 101, 60, 70))
    rows = [_row(i, "trend", 1, 60 + i) for i in range(10, 18)]
    trades = nonoverlapping_stream(candles, _cfg(), rows, "trend")
    assert [t.entry_index for t in trades] == [10, 16]


def test_reversal_sensitivity_reports_triggered_subset_both_ways():
    # one triggered row (score 65 >= 60, breadth 3, ALLOW). Opposite SETUP at
    # bar 12 closes the with-reversal run earlier than the no-reversal run.
    candles = _flat(12)
    candles.append(_bar(12, 100, 101, 99, 100))
    candles.append(_bar(13, 100, 101, 80, 85))
    rows = [_row(10, "trend", 1, 65),
            _row(11, "trend", 1, 30),  # sub-threshold: not triggered
            _row(12, "trend", 1, 30, decision_action="SETUP",
                 decision_direction=-1)]
    out = reversal_sensitivity(candles, _cfg(), rows, "trend")
    assert out["triggered_events"] == 1
    assert out["no_reversal"]["n"] == 1
    assert out["with_reversal"]["n"] == 1
    # with reversal: exit at bar 12 close 100 -> gross 0, net -0.025
    assert out["with_reversal"]["net_r"] == -0.025
    # without: rides to stop 92 at bar 13 -> net -2.025
    assert out["no_reversal"]["net_r"] == -2.025
    assert out["net_r_gap"] == 2.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_sim.py -v`
Expected: FAIL with `ImportError: cannot import name 'HypoTrade'`

- [ ] **Step 3: Append the implementation to `calibration.py`**

Re-add these imports to the import block (alongside the existing ones):
`from moonface.signal.engine.confluence import BASE_THRESHOLD, BREADTH_MIN, CT_SURCHARGE`
(merge into the existing `confluence` import line) and
`from moonface.signal.engine.position import PositionState, manage_position, open_position`.

```python
@dataclass(frozen=True)
class HypoTrade:
    entry_index: int
    exit_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    book: str
    direction: int
    score: int
    breadth: int
    policy: str | None
    macro_effective: str
    vol_state: str
    net_r: float
    bars_held: int
    exit_reason: str


def _row_state(row: BarRow, book: str) -> BookState:
    return row.trend if book == "trend" else row.revert


def simulate_entry(candles: list[Candle], cfg: EngineConfig, row: BarRow,
                   book: str,
                   rows_by_index: dict[int, BarRow] | None = None,
                   ) -> HypoTrade | None:
    """Open at row.index close with the frozen entry/exit discipline; manage
    bar-by-bar to EXIT. Returns None when the data ends first (caller counts
    incompletes). rows_by_index enables the opposite-SETUP reversal exit, used
    only by reversal_sensitivity — the primary panels pass None (spec §4b).

    ATR note: foundation.risk.atr averages the last `period` true ranges, so
    the (atr_period+1)-bar tail slice reproduces the full-history value
    exactly. manage_position reads only candles[-1], so each management step
    passes a single-bar list."""
    state = _row_state(row, book)
    profile = "WT" if book == "trend" else "CT"
    j = row.index
    tail = candles[max(0, j - cfg.atr_period):j + 1]
    sweep_wick = row.sweep_wick if profile == "CT" else None
    step = open_position(tail, cfg, state.direction, state.score / 100.0,
                         cfg.base_fraction, profile, sweep_wick)
    pos = PositionState(direction=state.direction,
                        entry_price=step.entry_price, stop=step.stop,
                        extreme=step.extreme, atr_at_entry=step.atr_at_entry,
                        fraction=cfg.base_fraction, bars_held=0,
                        profile=profile, target=step.target)
    for k in range(j + 1, len(candles)):
        signal_dir = 0
        if rows_by_index is not None:
            r_k = rows_by_index.get(k)
            if r_k is not None and r_k.decision_action == "SETUP":
                signal_dir = r_k.decision_direction
        step = manage_position([candles[k]], cfg, pos, signal_dir,
                               state.score / 100.0)
        if step.action == "EXIT":
            return HypoTrade(
                entry_index=j, exit_index=k, entry_ts_ms=row.ts_ms,
                exit_ts_ms=candles[k].timestamp_ms, book=book,
                direction=state.direction, score=state.score,
                breadth=state.breadth, policy=state.policy,
                macro_effective=row.macro_effective, vol_state=row.vol_state,
                net_r=step.realized_r, bars_held=step.bars_held,
                exit_reason=step.reason)
        pos = PositionState(direction=pos.direction,
                            entry_price=pos.entry_price, stop=step.stop,
                            extreme=step.extreme,
                            atr_at_entry=pos.atr_at_entry,
                            fraction=pos.fraction, bars_held=step.bars_held,
                            profile=profile, target=step.target)
    return None


def overlapping_panel(candles: list[Candle], cfg: EngineConfig,
                      rows: list[BarRow], book: str,
                      ) -> tuple[list[HypoTrade], dict]:
    """Primary calibration sample: EVERY directional, non-extreme-vol bar is a
    hypothetical entry (threshold-free). Overlap is handled at inference time
    by the moving-block bootstrap. Extreme-vol bars are excluded because the
    frozen decide() stands flat there at any score."""
    trades: list[HypoTrade] = []
    incomplete = 0
    skipped_extreme = 0
    for row in rows:
        state = _row_state(row, book)
        if state.direction == 0:
            continue
        if row.vol_state == "extreme":
            skipped_extreme += 1
            continue
        t = simulate_entry(candles, cfg, row, book)
        if t is None:
            incomplete += 1
        else:
            trades.append(t)
    return trades, {"events": len(trades), "incomplete": incomplete,
                    "skipped_extreme_vol": skipped_extreme}


def nonoverlapping_stream(candles: list[Candle], cfg: EngineConfig,
                          rows: list[BarRow], book: str) -> list[HypoTrade]:
    """Robustness sample: one position at a time per book (live sequencing
    shape, threshold-free)."""
    trades: list[HypoTrade] = []
    busy_until = -1
    for row in rows:
        if row.index <= busy_until:
            continue
        state = _row_state(row, book)
        if state.direction == 0 or row.vol_state == "extreme":
            continue
        t = simulate_entry(candles, cfg, row, book)
        if t is None:
            break
        trades.append(t)
        busy_until = t.exit_index
    return trades


def reversal_sensitivity(candles: list[Candle], cfg: EngineConfig,
                         rows: list[BarRow], book: str) -> dict:
    """Bound the no-reversal assumption (spec §4b): the actual-trigger subset
    (frozen threshold + breadth + non-REJECT gate) simulated with and without
    the opposite-SETUP reversal exit."""
    rows_by_index = {r.index: r for r in rows}
    triggered: list[BarRow] = []
    for row in rows:
        state = _row_state(row, book)
        if state.direction == 0 or row.vol_state == "extreme":
            continue
        if state.policy in (None, "REJECT"):
            continue
        threshold = BASE_THRESHOLD + (CT_SURCHARGE
                                      if state.policy == "ALLOW_CT" else 0)
        if state.breadth >= BREADTH_MIN and state.score >= threshold:
            triggered.append(row)

    def _net(with_reversal: bool) -> tuple[int, float]:
        total, count = 0.0, 0
        for row in triggered:
            t = simulate_entry(candles, cfg, row, book,
                               rows_by_index if with_reversal else None)
            if t is not None:
                total += t.net_r
                count += 1
        return count, round(total, 4)

    n_no, r_no = _net(False)
    n_rev, r_rev = _net(True)
    return {"triggered_events": len(triggered),
            "no_reversal": {"n": n_no, "net_r": r_no},
            "with_reversal": {"n": n_rev, "net_r": r_rev},
            "net_r_gap": round(r_rev - r_no, 4)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_sim.py tests/test_engine_calibration_pass.py -v`
Expected: all pass (Task 1 tests must still pass)

- [ ] **Step 5: Ruff**

Run: `.venv/bin/python -m ruff check src/moonface/signal/engine/calibration.py tests/test_engine_calibration_sim.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/calibration.py tests/test_engine_calibration_sim.py
git diff --cached --stat   # verify exactly these 2 files
git commit -m "feat(engine): calibration hypothetical-trade simulator (frozen exits, panels, reversal bound)"
```

---

### Task 3: Statistics — ranks, Spearman, block bootstrap, buckets, NW t, module IC

**Files:**
- Modify: `src/moonface/signal/engine/calibration.py` (append)
- Test: `tests/test_engine_calibration_stats.py`

**Interfaces:**
- Consumes: `HypoTrade`, `BarRow`, constants (Tasks 1–2)
- Produces:
  - `spearman(xs: list[float], ys: list[float]) -> float | None` (None when n<3 or a side is constant)
  - `block_bootstrap_rho_ci(trades: list[HypoTrade], block_bars=BLOCK_BARS, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED) -> tuple[float, float] | None`
  - `bucket_stats(trades: list[HypoTrade]) -> list[dict]` (4 dicts: `bucket`, `n`, `mean_net_r`)
  - `buckets_weakly_increasing(buckets: list[dict]) -> bool`
  - `nw_tstat_of_mean(z: list[float], lag=NW_LAG) -> float | None`
  - `module_ic_table(rows: list[BarRow], candles: list[Candle], horizon=IC_HORIZON_BARS) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_calibration_stats.py
"""Stdlib statistics for the calibration diagnostic (no numpy)."""
import math

from moonface.foundation.models import Candle
from moonface.signal.engine.calibration import (BarRow, BookState, HypoTrade,
                                                block_bootstrap_rho_ci,
                                                bucket_stats,
                                                buckets_weakly_increasing,
                                                module_ic_table,
                                                nw_tstat_of_mean, spearman)

H = 3_600_000


def _trade(i, score, net_r, entry_index=None):
    idx = entry_index if entry_index is not None else i
    return HypoTrade(entry_index=idx, exit_index=idx + 1,
                     entry_ts_ms=idx * H, exit_ts_ms=(idx + 1) * H,
                     book="trend", direction=1, score=score, breadth=3,
                     policy="ALLOW", macro_effective="NEUTRAL",
                     vol_state="normal", net_r=net_r, bars_held=1,
                     exit_reason="test")


def test_spearman_perfect_monotone_and_inverse():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert spearman(xs, [2.0, 4.0, 6.0, 8.0, 10.0]) == 1.0
    assert spearman(xs, [10.0, 8.0, 6.0, 4.0, 2.0]) == -1.0


def test_spearman_degenerate_returns_none():
    assert spearman([1.0, 2.0], [1.0, 2.0]) is None          # n < 3
    assert spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # constant side


def test_spearman_handles_ties_via_average_ranks():
    # xs ties: ranks [1, 2.5, 2.5, 4]
    rho = spearman([10.0, 20.0, 20.0, 30.0], [1.0, 2.0, 3.0, 4.0])
    assert rho is not None and 0.9 < rho <= 1.0


def test_bucket_stats_edges_and_means():
    trades = [_trade(0, 10, -1.0), _trade(1, 39, -1.0),   # <40
              _trade(2, 40, 0.0), _trade(3, 59, 0.2),     # 40-59
              _trade(4, 60, 0.5),                          # 60-74
              _trade(5, 75, 1.0), _trade(6, 100, 2.0)]     # >=75
    b = bucket_stats(trades)
    assert [x["n"] for x in b] == [2, 2, 1, 2]
    assert b[0]["mean_net_r"] == -1.0
    assert b[1]["mean_net_r"] == 0.1
    assert b[2]["mean_net_r"] == 0.5
    assert b[3]["mean_net_r"] == 1.5
    assert buckets_weakly_increasing(b) is True


def test_buckets_weakly_increasing_skips_empty_and_detects_decrease():
    inc = [{"bucket": "a", "n": 1, "mean_net_r": 0.0},
           {"bucket": "b", "n": 0, "mean_net_r": None},
           {"bucket": "c", "n": 1, "mean_net_r": 0.5}]
    dec = [{"bucket": "a", "n": 1, "mean_net_r": 0.5},
           {"bucket": "b", "n": 1, "mean_net_r": 0.0}]
    assert buckets_weakly_increasing(inc) is True
    assert buckets_weakly_increasing(dec) is False


def test_block_bootstrap_ci_positive_for_calibrated_fixture():
    # 400 events spread over many 168-bar blocks; net_r tracks score with a
    # small deterministic wiggle -> rho ~ 1, CI must exclude 0 from below.
    trades = [_trade(i, i % 101, (i % 101) / 100.0 + ((i % 7) - 3) * 0.01,
                     entry_index=i * 10) for i in range(400)]
    ci = block_bootstrap_rho_ci(trades)
    assert ci is not None
    assert ci[0] > 0


def test_block_bootstrap_ci_straddles_zero_for_unrelated_fixture():
    # net_r cycles independently of score -> rho ~ 0.
    trades = [_trade(i, i % 101, math.sin(i * 1.7), entry_index=i * 10)
              for i in range(400)]
    ci = block_bootstrap_rho_ci(trades)
    assert ci is not None
    assert ci[0] < 0 < ci[1]


def test_block_bootstrap_needs_two_blocks():
    trades = [_trade(i, i, 0.1, entry_index=i) for i in range(5)]  # 1 block
    assert block_bootstrap_rho_ci(trades) is None


def test_nw_tstat_of_mean():
    strong = [1.0 + 0.01 * (i % 3) for i in range(300)]
    weak = [(-1.0) ** i for i in range(300)]
    t_strong = nw_tstat_of_mean(strong)
    t_weak = nw_tstat_of_mean(weak)
    assert t_strong is not None and t_strong > 10
    assert t_weak is not None and abs(t_weak) < 2
    assert nw_tstat_of_mean([1.0] * 10) is None  # n < lag+2


def _row(index, points):
    return BarRow(index=index, ts_ms=index * H, macro_effective="NEUTRAL",
                  vol_state="normal", regime_trend=0,
                  trend=BookState(0, 0, 0, None),
                  revert=BookState(0, 0, 0, None),
                  module_points=points, sweep_wick=None,
                  decision_action="WAIT", decision_direction=0,
                  decision_score=0)


def test_module_ic_table_finds_predictive_module():
    # close rises iff m2_breakout was positive 24 bars earlier.
    n = 400
    signal = [1 if (i // 24) % 2 == 0 else -1 for i in range(n)]
    closes = [100.0]
    for i in range(1, n + 30):
        prev_sig = signal[i - 24] if 0 <= i - 24 < n else 0
        closes.append(closes[-1] * (1.0 + 0.001 * prev_sig))
    candles = [Candle(i * H, c, c, c, c, 1.0) for i, c in enumerate(closes)]
    rows = [_row(i, {"m2_breakout": 20 * signal[i], "m1_macro": 0})
            for i in range(n)]
    table = module_ic_table(rows, candles)
    by_name = {e["module"]: e for e in table}
    assert by_name["m2_breakout"]["rank_ic"] is not None
    assert by_name["m2_breakout"]["rank_ic"] > 0.5
    assert by_name["m1_macro"]["rank_ic"] is None  # constant zero -> None


def test_module_ic_table_empty_rows_is_safe():
    assert module_ic_table([], []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_stats.py -v`
Expected: FAIL with `ImportError: cannot import name 'spearman'`

- [ ] **Step 3: Append the implementation to `calibration.py`**

Re-add `import math` and `import random` to the import block.

```python
def _ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based) with tie averaging."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while (j + 1 < len(order)
               and values[order[j + 1]] == values[order[i]]):
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def block_bootstrap_rho_ci(trades: list["HypoTrade"],
                           block_bars: int = BLOCK_BARS,
                           draws: int = BOOTSTRAP_DRAWS,
                           seed: int = BOOTSTRAP_SEED,
                           ) -> tuple[float, float] | None:
    """95% CI for spearman(score, net_r) via a moving-block bootstrap keyed on
    entry-bar blocks (overlap-honest inference for the overlapping panel)."""
    blocks: dict[int, list[HypoTrade]] = {}
    for t in trades:
        blocks.setdefault(t.entry_index // block_bars, []).append(t)
    keys = sorted(blocks)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(draws):
        sample: list[HypoTrade] = []
        for _ in range(len(keys)):
            sample.extend(blocks[keys[rng.randrange(len(keys))]])
        rho = spearman([float(t.score) for t in sample],
                       [t.net_r for t in sample])
        if rho is not None:
            stats.append(rho)
    if len(stats) < draws // 2:
        return None
    stats.sort()
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(0.975 * (len(stats) - 1))]
    return (lo, hi)


def bucket_stats(trades: list["HypoTrade"]) -> list[dict]:
    e0, e1, e2 = BUCKET_EDGES
    bounds = [(0, e0), (e0, e1), (e1, e2), (e2, 10 ** 9)]
    out = []
    for lo, hi in bounds:
        rs = [t.net_r for t in trades if lo <= t.score < hi]
        label = f">={lo}" if hi >= 10 ** 9 else f"[{lo},{hi})"
        out.append({"bucket": label, "n": len(rs),
                    "mean_net_r": (round(sum(rs) / len(rs), 4)
                                   if rs else None)})
    return out


def buckets_weakly_increasing(buckets: list[dict]) -> bool:
    means = [b["mean_net_r"] for b in buckets if b["mean_net_r"] is not None]
    return all(b >= a for a, b in zip(means, means[1:]))


def nw_tstat_of_mean(z: list[float], lag: int = NW_LAG) -> float | None:
    """t-stat of mean(z) with Newey-West (Bartlett) long-run variance."""
    n = len(z)
    if n < lag + 2:
        return None
    mean = sum(z) / n
    d = [v - mean for v in z]
    var = sum(x * x for x in d) / n
    cov_sum = 0.0
    for el in range(1, lag + 1):
        w = 1.0 - el / (lag + 1.0)
        cov = sum(d[i] * d[i - el] for i in range(el, n)) / n
        cov_sum += 2.0 * w * cov
    lrv = var + cov_sum
    if lrv <= 0:
        return None
    se = math.sqrt(lrv / n)
    return mean / se if se > 0 else None


def _standardized_ranks(values: list[float]) -> list[float]:
    r = _ranks(values)
    n = len(r)
    m = sum(r) / n
    var = sum((a - m) ** 2 for a in r) / n
    if var == 0:
        return [0.0] * n
    sd = math.sqrt(var)
    return [(a - m) / sd for a in r]


def module_ic_table(rows: list[BarRow], candles: list[Candle],
                    horizon: int = IC_HORIZON_BARS) -> list[dict]:
    """SECONDARY diagnostic (spec §4d): per-module rank-IC vs forward log
    return, NW t. Suspect-ranking only — never verdict-bearing; fixed-horizon
    drift has repeatedly failed brackets in this program."""
    usable = [r for r in rows if r.index + horizon < len(candles)]
    out: list[dict] = []
    if not usable:
        return out
    fwd = [math.log(candles[r.index + horizon].close
                    / candles[r.index].close) for r in usable]
    for name in _TREND_MODULES + _REVERT_MODULES:
        xs = [float(r.module_points.get(name, 0)) for r in usable]
        rho = spearman(xs, fwd)
        if rho is None:
            out.append({"module": name, "rank_ic": None, "nw_t": None,
                        "n": len(usable)})
            continue
        rx = _standardized_ranks(xs)
        ry = _standardized_ranks(fwd)
        z = [a * b for a, b in zip(rx, ry)]
        t = nw_tstat_of_mean(z)
        out.append({"module": name, "rank_ic": round(rho, 4),
                    "nw_t": round(t, 3) if t is not None else None,
                    "n": len(usable)})
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_stats.py -v`
Expected: all pass

- [ ] **Step 5: Ruff**

Run: `.venv/bin/python -m ruff check src/moonface/signal/engine/calibration.py tests/test_engine_calibration_stats.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/calibration.py tests/test_engine_calibration_stats.py
git diff --cached --stat   # verify exactly these 2 files
git commit -m "feat(engine): calibration statistics (spearman, block bootstrap, NW t, module IC)"
```

---

### Task 4: Classification, verdict, and report assembly

**Files:**
- Modify: `src/moonface/signal/engine/calibration.py` (append)
- Test: `tests/test_engine_calibration_report.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3; `engine_hash(cfg)` from `moonface.signal.engine.config`
- Produces:
  - `classify_book(trades: list[HypoTrade], first_ts: int, last_ts: int) -> dict` — keys `events`, `events_score_ge_60`, `spearman_rho`, `rho_ci_95`, `buckets`, `buckets_weakly_increasing`, `rho_first_half`, `rho_second_half`, `stability_sign_agrees`, `status` (`"pass"|"fail"|"underpowered"`)
  - `overall_verdict(trend_status: str, revert_status: str) -> str` — `"CALIBRATED"|"PARTIALLY_CALIBRATED"|"UNCALIBRATED"|"UNDERPOWERED"`
  - `split_summary(trades, key_fn) -> dict[str, dict]`
  - `build_report(cfg: EngineConfig, candles: list[Candle], warmup: int) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_calibration_report.py
"""Pre-registered classification (spec §4c) + report assembly + degenerates."""
import math
import random

from moonface.foundation.models import Candle
from moonface.signal.engine.calibration import (HypoTrade, build_report,
                                                classify_book,
                                                overall_verdict,
                                                split_summary)
from moonface.signal.engine.config import EngineConfig

H = 3_600_000


def _trade(i, score, net_r, policy="ALLOW", direction=1, vol="normal"):
    return HypoTrade(entry_index=i * 10, exit_index=i * 10 + 1,
                     entry_ts_ms=i * 10 * H, exit_ts_ms=(i * 10 + 1) * H,
                     book="trend", direction=direction, score=score,
                     breadth=3, policy=policy, macro_effective="NEUTRAL",
                     vol_state=vol, net_r=net_r, bars_held=1,
                     exit_reason="test")


def _calibrated_fixture(n=400):
    # score in 0..100, net_r follows score with small deterministic wiggle;
    # >=60 count is ~40% of n -> both floors met; both halves positive rho.
    return [_trade(i, i % 101, (i % 101) / 100.0 + ((i % 7) - 3) * 0.01)
            for i in range(n)]


def test_classify_book_pass():
    trades = _calibrated_fixture()
    last_ts = trades[-1].entry_ts_ms
    out = classify_book(trades, first_ts=0, last_ts=last_ts)
    assert out["status"] == "pass"
    assert out["spearman_rho"] > 0.9
    assert out["rho_ci_95"][0] > 0
    assert out["buckets_weakly_increasing"] is True
    assert out["stability_sign_agrees"] is True
    assert out["events"] == 400
    assert out["events_score_ge_60"] >= 30


def test_classify_book_fail_on_inverted_score():
    trades = [_trade(i, i % 101, -(i % 101) / 100.0 + ((i % 7) - 3) * 0.01)
              for i in range(400)]
    out = classify_book(trades, first_ts=0, last_ts=trades[-1].entry_ts_ms)
    assert out["status"] == "fail"
    assert out["spearman_rho"] < 0


def test_classify_book_underpowered_beats_pass_and_fail():
    few = _calibrated_fixture(50)  # n < 200 -> underpowered even though rho>0
    out = classify_book(few, first_ts=0, last_ts=few[-1].entry_ts_ms)
    assert out["status"] == "underpowered"


def test_overall_verdict_matrix():
    assert overall_verdict("pass", "pass") == "CALIBRATED"
    assert overall_verdict("pass", "fail") == "PARTIALLY_CALIBRATED"
    assert overall_verdict("pass", "underpowered") == "PARTIALLY_CALIBRATED"
    assert overall_verdict("fail", "fail") == "UNCALIBRATED"
    assert overall_verdict("fail", "underpowered") == "UNCALIBRATED"
    assert overall_verdict("underpowered", "underpowered") == "UNDERPOWERED"


def test_split_summary_groups_and_means():
    trades = [_trade(0, 50, 1.0, policy="ALLOW"),
              _trade(1, 50, 0.0, policy="ALLOW"),
              _trade(2, 50, -1.0, policy="REJECT")]
    out = split_summary(trades, lambda t: t.policy or "NONE")
    assert out["ALLOW"] == {"n": 2, "mean_net_r": 0.5}
    assert out["REJECT"] == {"n": 1, "mean_net_r": -1.0}


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


def test_build_report_end_to_end_on_synthetic_series():
    candles = _walk_series(560, seed=11)
    cfg = EngineConfig(lookback_bars=400)
    report = build_report(cfg, candles, warmup=380)
    assert report["verdict"] in ("CALIBRATED", "PARTIALLY_CALIBRATED",
                                 "UNCALIBRATED", "UNDERPOWERED")
    assert set(report["books"]) == {"trend", "mean_revert"}
    for book in report["books"].values():
        assert "calibration" in book and "splits" in book
        assert "nonoverlapping" in book and "reversal_sensitivity" in book
        assert "panel_counts" in book
    assert len(report["module_ic_secondary"]) in (0, 12)
    assert report["engine_hash"] == (
        "10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf")
    assert "deriv=None" in " ".join(report["assumptions"])
    assert isinstance(report["data"]["fingerprint_sha256"], str)
    # small synthetic sample must be honestly underpowered, not opined on
    assert report["verdict"] == "UNDERPOWERED"


def test_build_report_empty_and_flat_inputs_are_safe():
    cfg = EngineConfig(lookback_bars=400)
    # fewer candles than warmup -> zero rows
    tiny = _walk_series(50)
    report = build_report(cfg, tiny, warmup=380)
    assert report["verdict"] == "UNDERPOWERED"
    # constant prices -> books never directional -> zero events
    flat = [Candle(i * H, 100.0, 100.0, 100.0, 100.0, 1.0)
            for i in range(450)]
    report2 = build_report(cfg, flat, warmup=420)
    assert report2["verdict"] == "UNDERPOWERED"
    assert report2["books"]["trend"]["panel_counts"]["events"] == 0
    assert not math.isnan(
        report2["data"]["first_scored_ts_ms"] or 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'classify_book'`

- [ ] **Step 3: Append the implementation to `calibration.py`**

Add `from moonface.signal.engine.config import EngineConfig, engine_hash` (merge
`engine_hash` into the existing config import line).

```python
def classify_book(trades: list[HypoTrade], first_ts: int,
                  last_ts: int) -> dict:
    """Pre-registered book classification (spec §4c). Power floor applies
    REGARDLESS of whether the statistics would pass or fail."""
    n = len(trades)
    trig_n = sum(1 for t in trades if t.score >= BASE_THRESHOLD)
    rho = spearman([float(t.score) for t in trades],
                   [t.net_r for t in trades])
    ci = block_bootstrap_rho_ci(trades)
    buckets = bucket_stats(trades)
    mono = buckets_weakly_increasing(buckets)
    mid = first_ts + (last_ts - first_ts) // 2
    h1 = [t for t in trades if t.entry_ts_ms < mid]
    h2 = [t for t in trades if t.entry_ts_ms >= mid]
    rho_h1 = spearman([float(t.score) for t in h1], [t.net_r for t in h1])
    rho_h2 = spearman([float(t.score) for t in h2], [t.net_r for t in h2])
    stable = (rho_h1 is not None and rho_h2 is not None
              and (rho_h1 > 0) == (rho_h2 > 0))
    underpowered = n < PANEL_FLOOR or trig_n < TRIGGER_BUCKET_FLOOR
    passes = (rho is not None and rho > 0
              and ci is not None and ci[0] > 0
              and mono and stable)
    status = ("underpowered" if underpowered
              else ("pass" if passes else "fail"))
    return {
        "events": n,
        "events_score_ge_60": trig_n,
        "spearman_rho": round(rho, 4) if rho is not None else None,
        "rho_ci_95": ([round(ci[0], 4), round(ci[1], 4)]
                      if ci is not None else None),
        "buckets": buckets,
        "buckets_weakly_increasing": mono,
        "rho_first_half": round(rho_h1, 4) if rho_h1 is not None else None,
        "rho_second_half": round(rho_h2, 4) if rho_h2 is not None else None,
        "stability_sign_agrees": stable,
        "status": status,
    }


def overall_verdict(trend_status: str, revert_status: str) -> str:
    statuses = (trend_status, revert_status)
    if all(s == "pass" for s in statuses):
        return "CALIBRATED"
    if any(s == "pass" for s in statuses):
        return "PARTIALLY_CALIBRATED"
    if any(s == "fail" for s in statuses):
        return "UNCALIBRATED"
    return "UNDERPOWERED"


def split_summary(trades: list[HypoTrade], key_fn) -> dict[str, dict]:
    groups: dict[str, list[float]] = {}
    for t in trades:
        groups.setdefault(key_fn(t), []).append(t.net_r)
    return {k: {"n": len(v), "mean_net_r": round(sum(v) / len(v), 4)}
            for k, v in sorted(groups.items())}


ASSUMPTIONS = (
    "deriv=None throughout: verdict covers the PRICE-STRUCTURE core only "
    "(trend book caps at 85/100 without m5_funding; revert book lacks "
    "m4_fund_ct and m5_oi_flush)",
    "hypothetical trades below the frozen threshold are counterfactual: the "
    "live engine never takes them; they exist to measure score ordering",
    "primary panels run the frozen exit discipline WITHOUT the opposite-SETUP "
    "reversal exit (undefined sub-threshold); reversal_sensitivity bounds "
    "the distortion on the actual-trigger subset",
    "extreme-vol bars are excluded from entries: the frozen decide() stands "
    "flat there at any score (excluded counts reported)",
    "net_r is per-unit R from the frozen cost model; sizing fractions do not "
    "affect it",
    "halves split at the midpoint timestamp of the scored span "
    "(approximates the spec's calendar halves)",
)


def build_report(cfg: EngineConfig, candles: list[Candle],
                 warmup: int) -> dict:
    rows = scoring_pass(cfg, candles, warmup)
    first_ts = rows[0].ts_ms if rows else None
    last_ts = candles[-1].timestamp_ms if candles else None
    books: dict[str, dict] = {}
    for book in ("trend", "mean_revert"):
        panel, counts = overlapping_panel(candles, cfg, rows, book)
        stream = nonoverlapping_stream(candles, cfg, rows, book)
        stream_rho = spearman([float(t.score) for t in stream],
                              [t.net_r for t in stream])
        books[book] = {
            "panel_counts": counts,
            "calibration": classify_book(panel, first_ts or 0, last_ts or 0),
            "splits": {
                "policy": split_summary(panel, lambda t: t.policy or "NONE"),
                "direction": split_summary(
                    panel,
                    lambda t: "LONG" if t.direction > 0 else "SHORT"),
                "vol_state": split_summary(panel, lambda t: t.vol_state),
            },
            "nonoverlapping": {
                "events": len(stream),
                "spearman_rho": (round(stream_rho, 4)
                                 if stream_rho is not None else None),
            },
            "reversal_sensitivity": reversal_sensitivity(
                candles, cfg, rows, book),
        }
    verdict = overall_verdict(
        books["trend"]["calibration"]["status"],
        books["mean_revert"]["calibration"]["status"])
    return {
        "engine_hash": engine_hash(cfg),
        "label": DIAGNOSTIC_LABEL,
        "data": {
            "candles": len(candles),
            "scored_bars": len(rows),
            "first_scored_ts_ms": first_ts,
            "last_ts_ms": last_ts,
            "fingerprint_sha256": series_fingerprint(candles),
            "lookback_bars": cfg.lookback_bars,
            "warmup": warmup,
        },
        "frozen_analysis_constants": {
            "block_bars": BLOCK_BARS, "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "ic_horizon_bars": IC_HORIZON_BARS, "nw_lag": NW_LAG,
            "bucket_edges": list(BUCKET_EDGES),
            "panel_floor": PANEL_FLOOR,
            "trigger_bucket_floor": TRIGGER_BUCKET_FLOOR,
        },
        "assumptions": list(ASSUMPTIONS),
        "books": books,
        "module_ic_secondary": module_ic_table(rows, candles),
        "verdict": verdict,
    }
```

- [ ] **Step 4: Run the full calibration test set**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_pass.py tests/test_engine_calibration_sim.py tests/test_engine_calibration_stats.py tests/test_engine_calibration_report.py -v`
Expected: all pass

- [ ] **Step 5: Ruff**

Run: `.venv/bin/python -m ruff check src/moonface/signal/engine/calibration.py tests/test_engine_calibration_report.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/calibration.py tests/test_engine_calibration_report.py
git diff --cached --stat   # verify exactly these 2 files
git commit -m "feat(engine): calibration classification, verdict, and report assembly"
```

---

### Task 5: CLI `tools/engine_calibration.py` + full-suite green

**Files:**
- Create: `tools/engine_calibration.py`
- Test: `tests/test_engine_calibration_cli.py`

**Interfaces:**
- Consumes: `build_report(cfg, candles, warmup) -> dict` (Task 4); `load_engine_config(path) -> EngineConfig`, `load_bundle(asset, start_ms, end_ms, cache_dir) -> DataBundle` (frozen)
- Produces: `tools.engine_calibration.run(argv) -> int`, `build_parser()`, `main()` — same shape as `tools/engine_honest_report.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_calibration_cli.py
"""CLI wiring only — the pure report is tested in
tests/test_engine_calibration_report.py. load_bundle is monkeypatched; the
CLI never fetches in tests."""
import json
import random

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from tools.engine_calibration import build_parser, run

H = 3_600_000


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


def test_parser_defaults():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1"])
    assert args.engine == "promotion/engine.json"
    assert args.cache_dir == ".backtest_cache"
    assert args.warmup == 6000
    assert args.out is None


def test_run_writes_report_json(tmp_path, monkeypatch, capsys):
    candles = _walk_series(560, seed=11)
    monkeypatch.setattr(
        "tools.engine_calibration.load_bundle",
        lambda asset, start_ms, end_ms, cache_dir: DataBundle(candles=candles))
    cfg_path = tmp_path / "engine.json"
    cfg_path.write_text(json.dumps({"lookback_bars": 400}))
    out_path = tmp_path / "report.json"
    rc = run(["--engine", str(cfg_path), "--start-ms", "0",
              "--end-ms", str(560 * H), "--warmup", "380",
              "--out", str(out_path)])
    assert rc == 0
    report = json.loads(out_path.read_text())
    assert report["verdict"] == "UNDERPOWERED"  # tiny synthetic sample
    assert set(report["books"]) == {"trend", "mean_revert"}
    printed = json.loads(capsys.readouterr().out)
    assert printed["verdict"] == report["verdict"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.engine_calibration'`

- [ ] **Step 3: Write the implementation**

```python
# tools/engine_calibration.py
"""Read-only score-calibration diagnostic for the frozen v2 engine.

Runs the calibration scoring pass + hypothetical-trade panels over historical
1h candles and emits the pre-registered report JSON (spec:
docs/research-log/specs/2026-07-04-v2-calibration-diagnostic-design.md;
frozen criteria: experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md).

DIAGNOSTIC ONLY — never gates, never mutates state, never recommends a
constant change. Touches no frozen value; the forward-paper clock is
unaffected.

Usage:
  .venv/bin/python -m tools.engine_calibration \
      --start-ms 1577836800000 --end-ms 1782316800000 \
      --out experiments/engine/calibration_report_2026-07.json
"""
from __future__ import annotations

import argparse
import json

from moonface.foundation.bundle import load_bundle
from moonface.signal.engine.calibration import build_report
from moonface.signal.engine.config import load_engine_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-calibration")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000,
                   help="first scored bar has a full lookback window; 6000 "
                        "keeps the 1W macro gate live from bar one")
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms,
                         args.cache_dir)
    report = build_report(cfg, bundle.candles, args.warmup)
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine_calibration_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Full suite + ruff (whole-lane gate)**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: everything green except any pre-existing known failures unrelated to this lane (report them verbatim if seen; do NOT fix unrelated tests).
Run: `.venv/bin/python -m ruff check src tools tests`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add tools/engine_calibration.py tests/test_engine_calibration_cli.py
git diff --cached --stat   # verify exactly these 2 files
git commit -m "feat(engine): engine-calibration CLI (read-only diagnostic report)"
```

---

### Task 6: Freeze the report skeleton BEFORE the run

**Files:**
- Create: `experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md`

**Interfaces:**
- Consumes: spec §4c criteria (verbatim), Task 4 verdict vocabulary
- Produces: the frozen criteria document the run's results get appended to

- [ ] **Step 1: Write the skeleton**

```markdown
# Confluence Engine v2 — Score-Calibration Diagnostic (2026-07)

**STATUS: CRITERIA FROZEN (pre-run). Results section empty until the single
registered run completes; criteria may not change afterward.**

Spec: `docs/research-log/specs/2026-07-04-v2-calibration-diagnostic-design.md`
Tooling: `src/moonface/signal/engine/calibration.py`, `tools/engine_calibration.py`
Engine identity: frozen v2, `engine_hash
10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf` — this lane
is READ-ONLY: no frozen constant, config, journal, or registration text is
touched, and the forward-paper clock is unaffected.

## The one question

Does the v2 confluence score order trade outcomes on history? If score buckets
do not order by expectancy, the weights are noise and no threshold placement
can fix it.

## Registered run (frozen)

- Command: `.venv/bin/python -m tools.engine_calibration
  --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000
  --out experiments/engine/calibration_report_2026-07.json`
- Data: cached `BTC/USDT:USDT` 1h perp (`.backtest_cache`), 2020-01 →
  2026-06; series fingerprint recorded by the tool in the report JSON.
- One run. Re-runs are permitted only for mechanical failure (crash,
  truncated data), never to revisit a completed result.

## Frozen criteria (spec §4c, verbatim semantics)

- **Primary, per book (TREND and MEAN_REVERT separately):** Spearman ρ between
  score-at-entry and net R over the overlapping hypothetical-trade panel.
  *Pass* = ρ > 0 with 95% moving-block-bootstrap CI excluding 0 (block 168
  bars, 1000 draws, seed 20260704), AND bucket mean net R weakly increasing
  across score buckets <40, 40–59, 60–74, ≥75 (point estimates; empty buckets
  skipped), AND sign of ρ agrees across the first/second halves of the scored
  span (midpoint split).
- **Power floor (applies regardless of pass/fail):** a book with < 200 panel
  events, or < 30 events at score ≥ 60, is UNDERPOWERED.
- **Verdict (one, written once):** CALIBRATED = both books pass;
  PARTIALLY_CALIBRATED = exactly one passes; UNCALIBRATED = neither passes
  and at least one affirmatively fails; UNDERPOWERED = both books below the
  floor.
- **Reported, never gated:** policy / direction / vol-state splits;
  non-overlapping stream ρ (robustness); reversal-sensitivity bound;
  per-module rank-IC table (SECONDARY suspect-ranking only — fixed-horizon
  drift is not evidence of tradeable quality in this program's record).

## Assumptions (first-class caveats)

1. `deriv=None`: the verdict covers the PRICE-STRUCTURE core only (trend book
   caps at 85/100; revert book lacks its two derivative modules). The live
   engine additionally sees derivatives confirmation.
2. Sub-threshold hypothetical trades are counterfactual — the engine never
   takes them; they exist to measure score ordering.
3. Primary panels omit the opposite-SETUP reversal exit (undefined
   sub-threshold); the reversal-sensitivity block bounds the distortion on
   the actual-trigger subset.
4. Extreme-vol bars are excluded from entries (frozen `decide()` stands flat
   there at any score); excluded counts are reported.

## What this diagnostic can and cannot conclude

It interprets the frozen forward record's meaning (is the score measuring
anything?). It CANNOT: validate an edge, recommend constant changes, or
trigger any engine action. Any future v2.1 is a separate human decision
requiring a new ENGINE_VERSION → new hash → new registration.

## Results (EMPTY until the registered run)

_To be appended: report JSON path, key numbers per book, splits, module IC
table, and the single verdict._

## Verdict

_To be written once, from the frozen criteria above._
```

- [ ] **Step 2: Verify the criteria match the spec**

Read `docs/research-log/specs/2026-07-04-v2-calibration-diagnostic-design.md`
§4c and confirm: same bucket edges, same floors (200 / 30), same bootstrap
constants (168 / 1000 / 20260704), same verdict vocabulary, power floor
applies regardless of pass/fail. Fix any drift in the skeleton (the spec
wins).

- [ ] **Step 3: Commit**

```bash
git add experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md
git diff --cached --stat   # verify exactly this 1 file
git commit -m "docs(engine): freeze calibration diagnostic criteria (pre-run skeleton)"
```

---

### Task 7: Registered real-data run + results + verdict

**Files:**
- Create: `experiments/engine/calibration_report_2026-07.json` (tool output)
- Modify: `experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md` (append Results + Verdict ONLY; the frozen sections above them must not change)

**Interfaces:**
- Consumes: the Task 5 CLI, the Task 6 frozen criteria
- Produces: the committed diagnostic verdict

- [ ] **Step 1: Pre-run sanity**

```bash
git status --short           # tree clean apart from egg-info noise
ls -la .backtest_cache/BTC_USDT:USDT_1h.csv   # full-history cache exists
.venv/bin/python -c "from moonface.signal.engine.config import EngineConfig, engine_hash; print(engine_hash(EngineConfig()))"
```
Expected hash: `10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf`

- [ ] **Step 2: Run the registered command (long-running: run in background)**

```bash
.venv/bin/python -m tools.engine_calibration \
    --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
    --out experiments/engine/calibration_report_2026-07.json \
    > /tmp/calibration_run.log 2>&1
```
Expected: exits 0; JSON report written. The scoring pass costs about as much
as the honest-report replay over the same span (CPU-bound, potentially
hours) — use the harness's background-execution mechanism and check the log,
do not poll in a tight loop. If the run crashes or the data is truncated,
fix the mechanical issue and re-run (permitted by the skeleton); anything
else is one run only.

- [ ] **Step 3: Append Results + Verdict to the skeleton**

Fill the Results section with, per book: panel counts (events / incomplete /
skipped extreme-vol), ρ + CI, the four bucket rows (n + mean net R), half-split
ρs, non-overlapping ρ, reversal-sensitivity numbers, policy/direction/vol
splits; then the module-IC table; then write the single Verdict line using
the frozen vocabulary and 2–4 sentences of interpretation that stay within
the "can and cannot conclude" bounds. Copy numbers from the JSON verbatim —
no rounding beyond what the tool emitted, no adjectives like "promising".

- [ ] **Step 4: Verify nothing frozen changed**

```bash
git diff experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md
```
Expected: additions ONLY in the Results and Verdict sections.

```bash
.venv/bin/python -m pytest tests/test_engine_calibration_pass.py -q
```
Expected: pass (frozen hash still intact after the run).

- [ ] **Step 5: Commit**

```bash
git add experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md experiments/engine/calibration_report_2026-07.json
git diff --cached --stat   # verify exactly these 2 files
git commit -m "docs(engine): calibration diagnostic results + verdict (read-only, clock untouched)"
```

---

## Plan self-review notes (already applied)

- Spec §2a rich row → Task 1 `BarRow`; §2a simulator → Task 2; §2a aggregation
  → Tasks 3–4; §2b CLI → Task 5; §2c parity claim → Task 1 parity test;
  §3 data/fingerprint/warmup → Tasks 4–5, 7; §4a two samples → Task 2;
  §4b reversal bound → Task 2; §4c criteria → Task 4 + frozen skeleton Task 6;
  §4d secondary IC → Task 3; §5 test list → Tasks 1–5 (parity, hash
  invariance, simulator hand-computed, aggregation fixtures incl. monotone→
  CALIBRATED-shape and shuffled→straddling-zero, degenerate inputs); §6
  ordering → Task 6 before Task 7.
- `profile follows the book` (spec §2a) is encoded in `simulate_entry`
  (`"WT" if book == "trend" else "CT"`).
- Type consistency: `HypoTrade.exit_index` exists for
  `nonoverlapping_stream`'s busy-window; `classify_book` consumes
  `entry_ts_ms`; `overall_verdict` consumes the `status` strings produced by
  `classify_book`.
