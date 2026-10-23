# v3 Backtest Evaluation Instrument Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pre-registered, read-only instrument that fits a minimal set of v3 constants on a train window, kills/selects on validation, and confirms once on a sealed latest-year window plus an ETH/SOL transfer test — all judged apples-to-apples against frozen v2.2.

**Architecture:** One analysis module `src/moonface/signal/engine/v3/evaluate.py` (read-only; never gates capital, never edits the engine), one CLI `tools/v3_evaluate.py`, one frozen pre-registration doc. Trades come from a one-position-at-a-time simulator that reuses the frozen v2.2 ATR bracket (`position.open_position`/`manage_position`), so v3 and v2.2 differ only in entry selection. All bootstrap/segmentation/isotonic machinery is reused from `repair.py`; the v2.2 baseline reuses `repair.qualifier_stream`+`replay_metrics`.

**Tech Stack:** Python 3.11+, stdlib only (no numpy). Tests via pytest in `tests/`. Spec: `docs/research-log/specs/2026-07-06-v3-eval-instrument-design.md`.

## Global Constraints

- **Read-only.** `evaluate.py` never gates capital, never mutates state, never edits any engine file. No edits to `config_v3.py`, `decide.py`, `matrix.py`, or any committed v3/v2.2 source. v2.2 hash `b4924f8e…` stays pinned; the v3 files stay as committed.
- **Stdlib only.** No numpy. Bootstrap via `repair.block_ci_q` (which uses `random.Random(seed)`).
- **Run commands:** `.venv/bin/pytest …` and `.venv/bin/python -m tools.v3_evaluate …`. Never bare `python`, never `rtk python`.
- **Git:** no AI attribution trailers. Never chain `git add && git commit` blindly — stage, check `git diff --cached --stat`, then commit. `docs/` is globally gitignored; spec/plan already committed with `-f` — do not re-add them in feature commits.
- **Frozen analysis constants (from spec §3–§5, copied verbatim, tested in Task 1):** `SPAN_START_TS_MS=1577836800000` (2020-01-01), `TRAIN_END_TS_MS=1704067200000` (2024-01-01), `SEALED_START_TS_MS=1751328000000` (2025-07-01), `SPAN_END_TS_MS=1782316800000` (2026-07-01), `PURGE_MS=repair.PURGE_MS`, exit bracket `K_STOP=2.0 K_TRAIL=3.0 MAX_BARS=96 ATR_PERIOD=14` (must equal `EngineConfig()` defaults), `EFFECTIVE_TRIALS=12` (`N_MECHANISMS=3 + N_ACTIVE_CELLS=9`), `FAMILY_ALPHA=0.05`, `CI_LO_Q=0.05/12/2`, `CI_HI_Q=1−CI_LO_Q`, `MIN_MECH_TRADES=30`, `MIN_CELL_TRADES=30`, `MIN_TRANSFER_TRADES=20`, `PANEL_FLOOR=calibration.PANEL_FLOOR` (200), `LOOKBACK=400`.
- **Gate metric = unweighted net-R** (sum of raw `net_r`); size-weighted net-R is a non-gated diagnostic only.
- **Sealed discipline:** nothing evaluates the sealed/ETH/SOL segments except inside `build_eval_report`'s gate flow, and only if validation (Gate 1) passes.
- **TDD:** every task writes its failing test first, verifies failure, implements, verifies pass, commits.

---

### Task 1: Frozen constants, `V3Trade`, chronological segmentation

**Files:**
- Create: `src/moonface/signal/engine/v3/evaluate.py`
- Test: `tests/test_v3_eval_splits.py`

**Interfaces:**
- Consumes: `repair.PURGE_MS`, `repair.segment_panel`; `calibration.PANEL_FLOOR`; `EngineConfig` (v2.2, for the bracket-const assertion).
- Produces: module constants listed in Global Constraints; `V3Trade` (frozen dataclass: `entry_index:int, exit_index:int, entry_ts_ms:int, exit_ts_ms:int, direction:int, mechanism:str, quality:float, risk_fraction:float, net_r:float, bars_held:int, exit_reason:str, cell:str`); `segment_v3(trades) -> tuple[dict[str,list[V3Trade]], int]` (delegates to `repair.segment_panel` with the frozen boundaries).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_splits.py
"""Frozen eval constants + leakage-safe chronological segmentation."""
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.evaluate import (
    ATR_PERIOD,
    CI_LO_Q,
    EFFECTIVE_TRIALS,
    K_STOP,
    K_TRAIL,
    MAX_BARS,
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    V3Trade,
    segment_v3,
)

H = 3_600_000


def _t(entry_i, exit_i):
    return V3Trade(entry_index=entry_i, exit_index=exit_i,
                   entry_ts_ms=entry_i * H, exit_ts_ms=exit_i * H,
                   direction=1, mechanism="BREAKOUT", quality=0.5,
                   risk_fraction=0.005, net_r=0.1, bars_held=exit_i - entry_i,
                   exit_reason="target", cell="TRENDING_UP/NORMAL")


def test_frozen_constants():
    assert TRAIN_END_TS_MS == 1704067200000     # 2024-01-01
    assert SEALED_START_TS_MS == 1751328000000  # 2025-07-01
    assert EFFECTIVE_TRIALS == 12
    assert abs(CI_LO_Q - 0.05 / 12 / 2) < 1e-15


def test_bracket_consts_match_v22_defaults():
    d = EngineConfig()
    assert (K_STOP, K_TRAIL, MAX_BARS, ATR_PERIOD) == \
        (d.k_stop, d.k_trail, d.max_bars, d.atr_period)


def test_segment_v3_routes_by_boundaries():
    train_end_h = TRAIN_END_TS_MS // H
    sealed_start_h = SEALED_START_TS_MS // H
    trades = [
        _t(train_end_h - 20, train_end_h - 10),          # train
        _t(train_end_h + 200, sealed_start_h - 10),       # validation
        _t(sealed_start_h + 200, sealed_start_h + 210),   # sealed
    ]
    segs, dropped = segment_v3(trades)
    assert len(segs["train"]) == 1
    assert len(segs["validation"]) == 1
    assert len(segs["sealed"]) == 1
    assert dropped == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_splits.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.evaluate'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/evaluate.py
"""Pre-registered, read-only backtest evaluation of the v3 engine.

Fits a minimal set of v3 constants (per-mechanism q_floors + matrix cell
pruning) on a train window, kills/selects on validation, and confirms once on a
sealed latest-year window plus an ETH/SOL transfer test — all judged
apples-to-apples against frozen v2.2 (identical exits). Never gates capital,
never edits the engine. Any promotion is a human decision.

Spec:   docs/research-log/specs/2026-07-06-v3-eval-instrument-design.md
Pre-reg: experiments/engine/ENGINE_V3_EVAL_2026-07.md
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.signal.engine.calibration import PANEL_FLOOR
from moonface.signal.engine.repair import PURGE_MS, segment_panel

# --- frozen split boundaries (spec §3) --------------------------------------
SPAN_START_TS_MS = 1577836800000     # 2020-01-01T00:00:00Z
TRAIN_END_TS_MS = 1704067200000      # 2024-01-01T00:00:00Z
SEALED_START_TS_MS = 1751328000000   # 2025-07-01T00:00:00Z
SPAN_END_TS_MS = 1782316800000       # 2026-07-01T00:00:00Z

# --- frozen exit bracket (spec §4.1; must equal EngineConfig() defaults) -----
K_STOP = 2.0
K_TRAIL = 3.0
MAX_BARS = 96
ATR_PERIOD = 14

# --- fit / inference constants (spec §4.4, §5) ------------------------------
N_MECHANISMS = 3
N_ACTIVE_CELLS = 9
EFFECTIVE_TRIALS = N_MECHANISMS + N_ACTIVE_CELLS   # 12
FAMILY_ALPHA = 0.05
CI_LO_Q = FAMILY_ALPHA / EFFECTIVE_TRIALS / 2.0
CI_HI_Q = 1.0 - CI_LO_Q
MIN_MECH_TRADES = 30
MIN_CELL_TRADES = 30
MIN_TRANSFER_TRADES = 20
LOOKBACK = 400

ASSETS = {
    "BTC": {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"},
    "ETH": {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "1h"},
    "SOL": {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "1h"},
}

EVAL_LABEL = ("v3 backtest evaluation — pre-registered; read-only; no capital "
              "gating; promotion is a human decision")

VERDICTS = (
    "CLOSED_NEGATIVE_VALIDATION",
    "CLOSED_NEGATIVE_SEALED_BTC",
    "CLOSED_NEGATIVE_TRANSFER",
    "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
)


@dataclass(frozen=True)
class V3Trade:
    entry_index: int
    exit_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    direction: int
    mechanism: str
    quality: float
    risk_fraction: float
    net_r: float
    bars_held: int
    exit_reason: str
    cell: str


def segment_v3(trades: list[V3Trade]) -> tuple[dict[str, list[V3Trade]], int]:
    """Leakage-safe train/validation/sealed split via the repair segmenter
    (train requires EXIT before train_end; later segments require ENTRY after
    boundary+purge)."""
    return segment_panel(trades, TRAIN_END_TS_MS, SEALED_START_TS_MS, PURGE_MS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_splits.py -q`
Expected: 3 passed. `segment_panel` reads `.entry_ts_ms`/`.exit_ts_ms`, which `V3Trade` provides.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_splits.py
git diff --cached --stat
git commit -m "feat(v3-eval): frozen constants, V3Trade, segmentation"
```

---

### Task 2: v3 trade simulator (frozen v2.2 ATR bracket)

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_bracket.py`

**Interfaces:**
- Consumes: `position.open_position`, `position.manage_position`, `position.PositionState`; `foundation.risk.atr`; `EngineConfig` (v2.2); `Candle`; `V3Trade`.
- Produces: `simulate_bracket_v3(candles, entry_index, direction, quality, mechanism, cell, cfg_v22) -> V3Trade | None`. Uses the "WT" profile, `confidence=quality`, `fraction=cfg_v22.base_fraction`; returns `None` when the data ends before an exit.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_bracket.py
"""v3 entry simulator reuses the frozen v2.2 ATR bracket for both directions."""
import dataclasses

from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.evaluate import simulate_bracket_v3

from tests.helpers_v3 import downtrend, uptrend

CFG22 = EngineConfig()


def test_long_bracket_exits_with_positive_r_in_uptrend():
    candles = uptrend(200, step=1.0)
    tr = simulate_bracket_v3(candles, 60, 1, 0.7, "BREAKOUT",
                             "TRENDING_UP/NORMAL", CFG22)
    assert tr is not None
    assert tr.direction == 1
    assert tr.exit_index > tr.entry_index
    assert tr.net_r > 0
    assert tr.exit_reason != ""


def test_short_bracket_exits_with_positive_r_in_downtrend():
    candles = downtrend(200, step=1.0)
    tr = simulate_bracket_v3(candles, 60, -1, 0.7, "BREAKOUT",
                             "TRENDING_DOWN/NORMAL", CFG22)
    assert tr is not None and tr.direction == -1 and tr.net_r > 0


def test_returns_none_when_data_ends_before_exit():
    candles = uptrend(70, step=0.01, wick=0.0)  # flat, near data end
    tr = simulate_bracket_v3(candles, 68, 1, 0.5, "PULLBACK",
                             "TRENDING_UP/QUIET", CFG22)
    assert tr is None


def test_metadata_is_carried_through():
    candles = uptrend(200, step=1.0)
    tr = simulate_bracket_v3(candles, 60, 1, 0.42, "REVERSION",
                             "RANGING/NORMAL", CFG22)
    assert tr.mechanism == "REVERSION" and tr.cell == "RANGING/NORMAL"
    assert tr.quality == 0.42
    assert tr.risk_fraction == CFG22.base_fraction
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_bracket.py -q`
Expected: FAIL with `ImportError: cannot import name 'simulate_bracket_v3'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- v3 trade simulator: frozen v2.2 ATR bracket (spec §4.1) -----------------
from moonface.foundation.models import Candle          # noqa: E402
from moonface.foundation.risk import atr               # noqa: E402
from moonface.signal.engine.config import EngineConfig  # noqa: E402
from moonface.signal.engine.position import (           # noqa: E402
    PositionState,
    manage_position,
    open_position,
)


def simulate_bracket_v3(candles: list[Candle], entry_index: int,
                        direction: int, quality: float, mechanism: str,
                        cell: str, cfg_v22: EngineConfig) -> V3Trade | None:
    """Open at entry_index close and manage bar-by-bar to EXIT with the frozen
    v2.2 WT bracket (k_stop/k_trail/max_bars). confidence=quality drives the
    target profile exactly as the v2.2 score/100 does. None if data ends first.
    """
    j = entry_index
    tail = candles[max(0, j - cfg_v22.atr_period):j + 1]
    step = open_position(tail, cfg_v22, direction, quality,
                         cfg_v22.base_fraction, "WT")
    pos = PositionState(direction=direction, entry_price=step.entry_price,
                        stop=step.stop, extreme=step.extreme,
                        atr_at_entry=step.atr_at_entry,
                        fraction=cfg_v22.base_fraction, bars_held=0,
                        profile="WT", target=step.target)
    for k in range(j + 1, len(candles)):
        step = manage_position([candles[k]], cfg_v22, pos, 0, quality)
        if step.action == "EXIT":
            return V3Trade(
                entry_index=j, exit_index=k,
                entry_ts_ms=candles[j].timestamp_ms,
                exit_ts_ms=candles[k].timestamp_ms, direction=direction,
                mechanism=mechanism, quality=quality,
                risk_fraction=cfg_v22.base_fraction, net_r=step.realized_r,
                bars_held=step.bars_held, exit_reason=step.reason, cell=cell)
        pos = PositionState(direction=pos.direction,
                            entry_price=pos.entry_price, stop=step.stop,
                            extreme=step.extreme,
                            atr_at_entry=pos.atr_at_entry,
                            fraction=pos.fraction, bars_held=step.bars_held,
                            profile="WT", target=step.target)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_bracket.py -q`
Expected: 4 passed. If `test_returns_none_when_data_ends_before_exit` instead exits (a flat series can still hit the time stop), shorten the series/entry so fewer than `MAX_BARS` bars remain after entry.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_bracket.py
git diff --cached --stat
git commit -m "feat(v3-eval): frozen v2.2 ATR bracket trade simulator"
```

---

### Task 3: Fit panel (overlapping, floor-free trigger stream)

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_fitpanel.py`

**Interfaces:**
- Consumes: `regime.classify_regime`, `regime.VolState`; `matrix.select_mechanism`, `matrix.MECHANISMS`; `mechanisms.base.build_context`; `simulate_bracket_v3`; `EngineConfigV3`, `EngineConfig`.
- Produces: `fit_panel(candles, cfg_v3, cfg_v22, lookback=LOOKBACK) -> list[V3Trade]`. Every regime-selected, non-extreme bar whose mechanism triggers (direction≠0) becomes a trade — **no q_floor filter, overlapping** (used only for train-window fitting). Records mechanism/quality/cell/net_r.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_fitpanel.py
"""Fit panel: floor-free overlapping trigger stream for train-window fitting."""
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import fit_panel

from tests.helpers_v3 import uptrend

CFG3 = EngineConfigV3()
CFG22 = EngineConfig()


def test_fit_panel_produces_trades_with_metadata():
    panel = fit_panel(uptrend(600), CFG3, CFG22, lookback=200)
    assert len(panel) > 0
    for tr in panel:
        assert tr.mechanism in ("BREAKOUT", "PULLBACK", "REVERSION")
        assert 0.0 <= tr.quality <= 1.0
        assert "/" in tr.cell


def test_fit_panel_is_overlapping_not_one_position():
    # floor-free overlapping stream: far more triggers than a one-position walk
    panel = fit_panel(uptrend(600), CFG3, CFG22, lookback=200)
    entries = [tr.entry_index for tr in panel]
    assert len(entries) == len(set(entries))  # one trade per triggering bar
    # overlapping: at least one trade opens before the previous one exits
    assert any(panel[i + 1].entry_index <= panel[i].exit_index
               for i in range(len(panel) - 1))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_fitpanel.py -q`
Expected: FAIL with `ImportError: cannot import name 'fit_panel'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- fit panel: floor-free overlapping trigger stream (spec §4.1–§4.3) -------
from moonface.signal.engine.v3.config_v3 import EngineConfigV3   # noqa: E402
from moonface.signal.engine.v3.matrix import (                   # noqa: E402
    MECHANISMS,
    select_mechanism,
)
from moonface.signal.engine.v3.mechanisms.base import build_context  # noqa: E402
from moonface.signal.engine.v3.regime import (                   # noqa: E402
    VolState,
    classify_regime,
)


def fit_panel(candles: list[Candle], cfg_v3: EngineConfigV3,
              cfg_v22: EngineConfig, lookback: int = LOOKBACK) -> list[V3Trade]:
    """Every regime-selected, non-extreme bar whose mechanism triggers becomes
    a trade (NO q_floor filter, overlapping). Train-window fitting only."""
    panel: list[V3Trade] = []
    start = min(lookback, len(candles))
    for i in range(start, len(candles)):
        window = candles[max(0, i - lookback + 1): i + 1]
        idx = len(window) - 1
        regime = classify_regime(window, cfg_v3)
        if regime.vol_state == VolState.EXTREME:
            continue
        name = select_mechanism(regime)
        if name is None:
            continue
        ctx = build_context(window, idx, cfg_v3)
        sig = MECHANISMS[name].evaluate(ctx, regime)
        if sig.direction == 0:
            continue
        cell = f"{regime.dir_state.value}/{regime.vol_state.value}"
        trade = simulate_bracket_v3(candles, i, sig.direction, sig.quality,
                                    name, cell, cfg_v22)
        if trade is not None:
            panel.append(trade)
    return panel
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_fitpanel.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_fitpanel.py
git diff --cached --stat
git commit -m "feat(v3-eval): floor-free overlapping fit panel"
```

---

### Task 4: Fit — per-mechanism q_floors (isotonic)

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_qfloor.py`

**Interfaces:**
- Consumes: `repair._pava_blocks`; `V3Trade`; `EngineConfigV3`; `MIN_MECH_TRADES`.
- Produces: `fit_q_floors(train: list[V3Trade], cfg_v3) -> dict[str, float]` (one floor per mechanism name; PAVA-isotonic `E[R]` on quality; floor = lowest quality where fitted `E[R] ≥ 0`; underpowered mechanism keeps its default floor).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_qfloor.py
"""q_floor fit: isotonic E[R] on quality; floor at first non-negative bucket."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import fit_q_floors

CFG3 = EngineConfigV3()


def _tr(mech, quality, net_r, i=[0]):
    from moonface.signal.engine.v3.evaluate import V3Trade
    i[0] += 1
    return V3Trade(entry_index=i[0], exit_index=i[0] + 1, entry_ts_ms=i[0],
                   exit_ts_ms=i[0] + 1, direction=1, mechanism=mech,
                   quality=quality, risk_fraction=0.005, net_r=net_r,
                   bars_held=1, exit_reason="target", cell="X/Y")


def test_floor_excludes_negative_low_quality_band():
    # low-quality BREAKOUT loses, high-quality wins -> floor lifts above the
    # losing band
    train = ([_tr("BREAKOUT", 0.30, -0.5) for _ in range(40)]
             + [_tr("BREAKOUT", 0.80, 0.6) for _ in range(40)])
    floors = fit_q_floors(train, CFG3)
    assert floors["BREAKOUT"] > 0.30
    assert floors["BREAKOUT"] <= 0.80


def test_underpowered_mechanism_keeps_default():
    train = [_tr("PULLBACK", 0.5, 0.1) for _ in range(5)]  # < MIN_MECH_TRADES
    floors = fit_q_floors(train, CFG3)
    assert floors["PULLBACK"] == CFG3.q_floor_pullback


def test_all_positive_gives_floor_at_or_below_min_quality():
    train = [_tr("REVERSION", 0.4 + 0.01 * (n % 20), 0.3) for n in range(40)]
    floors = fit_q_floors(train, CFG3)
    assert floors["REVERSION"] <= 0.4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_qfloor.py -q`
Expected: FAIL with `ImportError: cannot import name 'fit_q_floors'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- fit: per-mechanism q_floors via isotonic E[R] on quality (spec §4.2) ----
from moonface.signal.engine.repair import _pava_blocks   # noqa: E402

_DEFAULT_FLOOR = {
    "BREAKOUT": "q_floor_breakout",
    "PULLBACK": "q_floor_pullback",
    "REVERSION": "q_floor_reversion",
}


def fit_q_floors(train: list[V3Trade], cfg_v3: EngineConfigV3,
                 ) -> dict[str, float]:
    """Lowest quality at which train E[R] (isotonic in quality) is >= 0. A
    mechanism with < MIN_MECH_TRADES train trades keeps its default floor."""
    floors: dict[str, float] = {}
    for name, attr in _DEFAULT_FLOOR.items():
        default = getattr(cfg_v3, attr)
        rows = sorted(((t.quality, t.net_r) for t in train
                       if t.mechanism == name), key=lambda p: p[0])
        if len(rows) < MIN_MECH_TRADES:
            floors[name] = default
            continue
        qs = [q for q, _ in rows]
        means = [r for _, r in rows]
        weights = [1.0] * len(rows)
        blocks = _pava_blocks(means, weights)
        # expand block means back to per-observation fitted values
        fitted: list[float] = []
        for mean, _, size in blocks:
            fitted.extend([mean] * int(size))
        floor = default
        for q, f in zip(qs, fitted):
            if f >= 0.0:
                floor = q
                break
        else:
            floor = 1.0  # never non-negative -> effectively veto the mechanism
        floors[name] = floor
    return floors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_qfloor.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_qfloor.py
git diff --cached --stat
git commit -m "feat(v3-eval): isotonic per-mechanism q_floor fit"
```

---

### Task 5: Fit — matrix cell pruning

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_prune.py`

**Interfaces:**
- Consumes: `matrix.REGIME_MECHANISM`; `regime.DirState`, `regime.VolState`; `V3Trade`; `MIN_CELL_TRADES`.
- Produces: `prune_cells(train: list[V3Trade]) -> dict[tuple, str | None]` (a fitted copy of `REGIME_MECHANISM`: a live cell whose train net-R sign ≤ 0 or which has < MIN_CELL_TRADES trades becomes `None`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_prune.py
"""Cell pruning: negative-sign or underpowered train cells go flat."""
from moonface.signal.engine.v3.evaluate import prune_cells
from moonface.signal.engine.v3.matrix import REGIME_MECHANISM
from moonface.signal.engine.v3.regime import DirState, VolState


def _tr(cell, net_r, i=[0]):
    from moonface.signal.engine.v3.evaluate import V3Trade
    i[0] += 1
    return V3Trade(entry_index=i[0], exit_index=i[0] + 1, entry_ts_ms=i[0],
                   exit_ts_ms=i[0] + 1, direction=1, mechanism="BREAKOUT",
                   quality=0.5, risk_fraction=0.005, net_r=net_r, bars_held=1,
                   exit_reason="target", cell=cell)


def test_positive_cell_kept_negative_cell_pruned():
    up_norm = "TRENDING_UP/NORMAL"
    dn_norm = "TRENDING_DOWN/NORMAL"
    train = ([_tr(up_norm, 0.2) for _ in range(40)]
             + [_tr(dn_norm, -0.2) for _ in range(40)])
    fitted = prune_cells(train)
    assert fitted[(DirState.TRENDING_UP, VolState.NORMAL)] == "BREAKOUT"
    assert fitted[(DirState.TRENDING_DOWN, VolState.NORMAL)] is None


def test_underpowered_cell_pruned():
    train = [_tr("TRENDING_UP/NORMAL", 0.5) for _ in range(5)]
    fitted = prune_cells(train)
    assert fitted[(DirState.TRENDING_UP, VolState.NORMAL)] is None


def test_already_none_cell_stays_none():
    fitted = prune_cells([])
    assert fitted[(DirState.RANGING, VolState.HIGH)] is None
    # every fitted key exists in the original matrix
    assert set(fitted) == set(REGIME_MECHANISM)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_prune.py -q`
Expected: FAIL with `ImportError: cannot import name 'prune_cells'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- fit: matrix cell pruning (spec §4.3) -----------------------------------
from moonface.signal.engine.v3.matrix import REGIME_MECHANISM   # noqa: E402
from moonface.signal.engine.v3.regime import DirState, VolState  # noqa: E402


def prune_cells(train: list[V3Trade]) -> dict[tuple, str | None]:
    """Copy of REGIME_MECHANISM with each live cell pruned to None when its
    train net-R sign is <= 0 or it has < MIN_CELL_TRADES trades."""
    by_cell: dict[str, list[float]] = {}
    for t in train:
        by_cell.setdefault(t.cell, []).append(t.net_r)
    fitted: dict[tuple, str | None] = {}
    for (dir_state, vol_state), name in REGIME_MECHANISM.items():
        if name is None:
            fitted[(dir_state, vol_state)] = None
            continue
        cell = f"{dir_state.value}/{vol_state.value}"
        rs = by_cell.get(cell, [])
        keep = len(rs) >= MIN_CELL_TRADES and sum(rs) > 0.0
        fitted[(dir_state, vol_state)] = name if keep else None
    return fitted
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_prune.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_prune.py
git diff --cached --stat
git commit -m "feat(v3-eval): matrix cell pruning fit"
```

---

### Task 6: Fitted decision + non-overlapping trade stream

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_stream.py`

**Interfaces:**
- Consumes: `classify_regime`, `VolState`; `MECHANISMS`; `build_context`; `sizing.size_from_quality`; `simulate_bracket_v3`; `foundation.risk.atr`; a fitted `EngineConfigV3` (q_floors replaced) + a fitted matrix dict.
- Produces: `decide_fitted(window, index, cfg_v3_fitted, fitted_matrix) -> tuple[str,int,float,float,str] | None` (mechanism, direction, quality, risk_fraction, cell), applying the fitted floor + pruned matrix; `fitted_cfg(cfg_v3, q_floors) -> EngineConfigV3`; `v3_stream(candles, cfg_v3_fitted, fitted_matrix, cfg_v22, lookback=LOOKBACK) -> list[tuple[V3Trade, float]]` (one-position-at-a-time; pairs carry atr_frac for cost stress, matching `repair.replay_metrics`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_stream.py
"""Fitted one-position stream applies the fitted floor + pruned matrix."""
import dataclasses

from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import (
    fitted_cfg,
    prune_cells,
    v3_stream,
)
from moonface.signal.engine.v3.matrix import REGIME_MECHANISM

from tests.helpers_v3 import uptrend

CFG3 = EngineConfigV3()
CFG22 = EngineConfig()


def test_fitted_cfg_replaces_floors():
    cfg = fitted_cfg(CFG3, {"BREAKOUT": 0.5, "PULLBACK": 0.6, "REVERSION": 0.7})
    assert cfg.q_floor_breakout == 0.5 and cfg.q_floor_reversion == 0.7


def test_stream_is_one_position_and_non_overlapping():
    pairs = v3_stream(uptrend(600), CFG3, dict(REGIME_MECHANISM), CFG22,
                      lookback=200)
    prev_exit = -1
    for trade, atr_frac in pairs:
        assert trade.entry_index > prev_exit
        assert atr_frac > 0.0
        prev_exit = trade.exit_index


def test_pruned_matrix_suppresses_all_entries():
    empty = {k: None for k in REGIME_MECHANISM}
    assert v3_stream(uptrend(600), CFG3, empty, CFG22, lookback=200) == []


def test_high_floor_suppresses_all_entries():
    veto = fitted_cfg(CFG3, {"BREAKOUT": 1.0, "PULLBACK": 1.0,
                             "REVERSION": 1.0})
    assert v3_stream(uptrend(600), veto, dict(REGIME_MECHANISM), CFG22,
                     lookback=200) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_stream.py -q`
Expected: FAIL with `ImportError: cannot import name 'fitted_cfg'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- fitted decision + non-overlapping stream (spec §4.1, §5) ---------------
import dataclasses                                          # noqa: E402

from moonface.signal.engine.v3.sizing import size_from_quality  # noqa: E402


def fitted_cfg(cfg_v3: EngineConfigV3, q_floors: dict[str, float],
               ) -> EngineConfigV3:
    return dataclasses.replace(
        cfg_v3, q_floor_breakout=q_floors["BREAKOUT"],
        q_floor_pullback=q_floors["PULLBACK"],
        q_floor_reversion=q_floors["REVERSION"])


def decide_fitted(window: list[Candle], index: int,
                  cfg_v3_fitted: EngineConfigV3, fitted_matrix: dict,
                  ) -> tuple[str, int, float, float, str] | None:
    """decide_v3 logic with the FITTED matrix + FITTED q_floors. Returns
    (mechanism, direction, quality, risk_fraction, cell) or None (no trade).
    The engine's own decide.py is left untouched; this is the analysis twin."""
    regime = classify_regime(window, cfg_v3_fitted)
    if regime.vol_state == VolState.EXTREME:
        return None
    name = fitted_matrix.get((regime.dir_state, regime.vol_state))
    if name is None:
        return None
    ctx = build_context(window, index, cfg_v3_fitted)
    sig = MECHANISMS[name].evaluate(ctx, regime)
    if sig.direction == 0:
        return None
    frac = size_from_quality(name, sig.quality, cfg_v3_fitted)
    if frac == 0.0:
        return None
    cell = f"{regime.dir_state.value}/{regime.vol_state.value}"
    return (name, sig.direction, sig.quality, frac, cell)


def v3_stream(candles: list[Candle], cfg_v3_fitted: EngineConfigV3,
              fitted_matrix: dict, cfg_v22: EngineConfig,
              lookback: int = LOOKBACK) -> list[tuple[V3Trade, float]]:
    """One-position-at-a-time fitted stream; pairs carry atr_frac so
    repair.replay_metrics can compute cost stress unchanged."""
    pairs: list[tuple[V3Trade, float]] = []
    busy_until = -1
    start = min(lookback, len(candles))
    for i in range(start, len(candles)):
        if i <= busy_until:
            continue
        window = candles[max(0, i - lookback + 1): i + 1]
        decided = decide_fitted(window, len(window) - 1, cfg_v3_fitted,
                                fitted_matrix)
        if decided is None:
            continue
        name, direction, quality, frac, cell = decided
        trade = simulate_bracket_v3(candles, i, direction, quality, name,
                                    cell, cfg_v22)
        if trade is None:
            break
        trade = dataclasses.replace(trade, risk_fraction=frac)
        tail = candles[max(0, i - cfg_v22.atr_period):i + 1]
        close = candles[i].close
        atr_frac = atr(tail, cfg_v22.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_stream.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_stream.py
git diff --cached --stat
git commit -m "feat(v3-eval): fitted decision + one-position stream"
```

---

### Task 7: Metrics, v2.2 baseline, size-weighted diagnostic

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_metrics.py`

**Interfaces:**
- Consumes: `repair.replay_metrics`, `repair.qualifier_stream`; `calibration.scoring_pass`; `confluence.BASE_THRESHOLD`; `EngineConfig`.
- Produces: `v3_metrics(pairs, cfg_v22) -> dict` (delegates to `repair.replay_metrics`; adds `size_weighted_net_r`); `v22_pairs(candles, cfg_v22, warmup) -> list[tuple]` (v2.2 long-only trend stream pairs over the FULL series via `qualifier_stream`, so the 1W-macro warmup is intact and per-window baselines come from splitting, not re-slicing); `split_pairs_by_window(pairs, start_ts, end_ts) -> list` (pairs whose trade exits within `[start_ts, end_ts)`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_metrics.py
"""Metrics + v2.2 baseline reuse the repair replay machinery."""
import dataclasses

from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.evaluate import (
    V3Trade,
    split_pairs_by_window,
    v3_metrics,
)

CFG22 = EngineConfig()


def _pair(exit_ts, net_r, frac):
    tr = V3Trade(entry_index=0, exit_index=1, entry_ts_ms=0, exit_ts_ms=exit_ts,
                 direction=1, mechanism="BREAKOUT", quality=0.5,
                 risk_fraction=frac, net_r=net_r, bars_held=1,
                 exit_reason="target", cell="X/Y")
    return (tr, 0.02)


def test_v3_metrics_has_replay_keys_plus_size_weight():
    pairs = [_pair(10, 1.0, 0.02), _pair(20, -0.5, 0.005)]
    m = v3_metrics(pairs, CFG22)
    assert set(m) >= {"n", "net_r", "max_dd_r", "cost_stress",
                      "size_weighted_net_r"}
    assert m["n"] == 2
    # unweighted net_r is the plain sum; size-weighted scales by frac/base
    assert abs(m["net_r"] - 0.5) < 1e-9
    base = CFG22.base_fraction
    expect_w = 1.0 * (0.02 / base) + (-0.5) * (0.005 / base)
    assert abs(m["size_weighted_net_r"] - round(expect_w, 4)) < 1e-3


def test_split_pairs_by_window():
    pairs = [_pair(5, 1.0, 0.02), _pair(150, 1.0, 0.02), _pair(400, 1.0, 0.02)]
    got = split_pairs_by_window(pairs, 100, 300)
    assert [p[0].exit_ts_ms for p in got] == [150]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_metrics.py -q`
Expected: FAIL with `ImportError: cannot import name 'v3_metrics'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- metrics + v2.2 baseline (spec §3, §4.1) --------------------------------
from moonface.signal.engine.calibration import scoring_pass    # noqa: E402
from moonface.signal.engine.confluence import BASE_THRESHOLD   # noqa: E402
from moonface.signal.engine.repair import (                    # noqa: E402
    qualifier_stream,
    replay_metrics,
)


def v3_metrics(pairs: list[tuple[V3Trade, float]],
               cfg_v22: EngineConfig) -> dict:
    """Unweighted gate metrics (repair.replay_metrics) + a non-gated
    size-weighted net-R diagnostic (net_r scaled by risk_fraction/base)."""
    m = replay_metrics(pairs, cfg_v22)
    base = cfg_v22.base_fraction
    weighted = sum(t.net_r * (t.risk_fraction / base) for t, _ in pairs) \
        if base > 0 else 0.0
    m["size_weighted_net_r"] = round(weighted, 4)
    return m


def v22_pairs(candles: list[Candle], cfg_v22: EngineConfig,
              warmup: int) -> list:
    """Frozen v2.2 long-only trend stream over the FULL series (its actual live
    behavior), via the repair qualifier stream. Split the returned pairs by
    window for per-segment baselines — never re-slice the candles (that would
    strip the 1W-macro warmup and mix train trades into a later window)."""
    rows = scoring_pass(cfg_v22, candles, warmup)
    return qualifier_stream(
        candles, cfg_v22, rows,
        lambda row: row.trend.score >= BASE_THRESHOLD)


def split_pairs_by_window(pairs: list[tuple[V3Trade, float]],
                          start_ts: int, end_ts: int) -> list:
    return [p for p in pairs if start_ts <= p[0].exit_ts_ms < end_ts]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_metrics.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_metrics.py
git diff --cached --stat
git commit -m "feat(v3-eval): metrics, v2.2 baseline, size-weighted diagnostic"
```

---

### Task 8: Gate 1 — validation (cost, deflated CI, drawdown, power)

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_gate1.py`

**Interfaces:**
- Consumes: `repair.block_ci_q`; `v3_metrics`; `CI_LO_Q`, `CI_HI_Q`, `PANEL_FLOOR`.
- Produces: `gate1_validation(val_pairs, baseline_val) -> dict` with keys `n`, `net_r`, `net_r_3x`, `max_dd_r`, `baseline_max_dd_r`, `ci`, `passed`. Pass iff `n >= PANEL_FLOOR`, `net_r_3x > 0`, family-corrected block-CI lower bound `> 0`, and `abs(max_dd_r) <= abs(baseline_max_dd_r)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_gate1.py
"""Gate 1: validation with 3x cost, deflated block CI, drawdown, power floor."""
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.evaluate import V3Trade, gate1_validation

CFG22 = EngineConfig()
H = 3_600_000


def _pairs(n, net_r):
    out = []
    for i in range(n):
        tr = V3Trade(entry_index=i * 10, exit_index=i * 10 + 1,
                     entry_ts_ms=i * 10 * H, exit_ts_ms=(i * 10 + 1) * H,
                     direction=1, mechanism="BREAKOUT", quality=0.5,
                     risk_fraction=0.005, net_r=net_r, bars_held=1,
                     exit_reason="target", cell="X/Y")
        out.append((tr, 0.05))
    return out


def test_below_panel_floor_fails():
    g = gate1_validation(_pairs(50, 0.3), {"max_dd_r": -1.0})
    assert g["passed"] is False


def test_strong_positive_passes():
    g = gate1_validation(_pairs(300, 0.3), {"max_dd_r": -100.0})
    assert g["passed"] is True
    assert g["ci"][0] > 0 and g["net_r_3x"] > 0


def test_worse_drawdown_than_baseline_fails():
    g = gate1_validation(_pairs(300, 0.3), {"max_dd_r": -0.01})
    assert g["passed"] is False  # v3 drawdown deeper than the tiny baseline
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_gate1.py -q`
Expected: FAIL with `ImportError: cannot import name 'gate1_validation'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- Gate 1: validation (spec §5) -------------------------------------------
from moonface.signal.engine.repair import block_ci_q          # noqa: E402


def _mean_r(pairs: list) -> float | None:
    return sum(t.net_r for t, _ in pairs) / len(pairs) if pairs else None


def gate1_validation(val_pairs: list[tuple[V3Trade, float]],
                     baseline_val: dict) -> dict:
    m = v3_metrics(val_pairs, EngineConfig())
    ci = block_ci_q(val_pairs, lambda p: p[0].entry_index, _mean_r,
                    CI_LO_Q, CI_HI_Q)
    base_dd = baseline_val.get("max_dd_r", 0.0)
    passed = (len(val_pairs) >= PANEL_FLOOR
              and m["cost_stress"]["net_r_3x"] > 0
              and ci is not None and ci[0] > 0
              and abs(m["max_dd_r"]) <= abs(base_dd))
    return {"n": m["n"], "net_r": m["net_r"],
            "net_r_3x": m["cost_stress"]["net_r_3x"],
            "max_dd_r": m["max_dd_r"], "baseline_max_dd_r": base_dd,
            "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "passed": passed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_gate1.py -q`
Expected: 3 passed. If `test_strong_positive_passes` fails on the CI bound (bootstrap variance on a degenerate constant series), widen the `net_r` spread across trades in `_pairs`; do NOT loosen the gate.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_gate1.py
git diff --cached --stat
git commit -m "feat(v3-eval): Gate 1 validation criteria"
```

---

### Task 9: Gate 2 (sealed BTC) + Gate 3 (ETH/SOL transfer)

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_gate23.py`

**Interfaces:**
- Consumes: `v3_metrics`; `MIN_TRANSFER_TRADES`.
- Produces: `gate2_sealed(sealed_pairs, baseline_sealed) -> dict` (keys `n`, `net_r_3x`, `max_dd_r`, `baseline_max_dd_r`, `passed`; pass iff `net_r_3x > 0` and `abs(max_dd_r) <= abs(baseline_max_dd_r)`); `gate3_transfer(eth_pairs, sol_pairs) -> dict` (per-asset `n`/`net_r_3x`; pass iff BOTH have `n >= MIN_TRANSFER_TRADES` and `net_r_3x > 0`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_gate23.py
"""Gate 2 sealed BTC (sign+drawdown) and Gate 3 ETH/SOL transfer."""
from moonface.signal.engine.v3.evaluate import (
    V3Trade,
    gate2_sealed,
    gate3_transfer,
)

H = 3_600_000


def _pairs(n, net_r):
    out = []
    for i in range(n):
        tr = V3Trade(entry_index=i, exit_index=i + 1, entry_ts_ms=i * H,
                     exit_ts_ms=(i + 1) * H, direction=1, mechanism="BREAKOUT",
                     quality=0.5, risk_fraction=0.005, net_r=net_r,
                     bars_held=1, exit_reason="target", cell="X/Y")
        out.append((tr, 0.05))
    return out


def test_gate2_positive_sign_and_ok_drawdown_passes():
    g = gate2_sealed(_pairs(40, 0.2), {"max_dd_r": -100.0})
    assert g["passed"] is True


def test_gate2_worse_drawdown_fails():
    g = gate2_sealed(_pairs(40, 0.2), {"max_dd_r": -0.001})
    assert g["passed"] is False


def test_gate3_requires_both_assets_positive_and_powered():
    ok = gate3_transfer(_pairs(30, 0.2), _pairs(30, 0.2))
    assert ok["passed"] is True
    one_neg = gate3_transfer(_pairs(30, 0.2), _pairs(30, -0.2))
    assert one_neg["passed"] is False
    thin = gate3_transfer(_pairs(30, 0.2), _pairs(10, 0.2))  # SOL < floor
    assert thin["passed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_gate23.py -q`
Expected: FAIL with `ImportError: cannot import name 'gate2_sealed'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- Gate 2 (sealed BTC) + Gate 3 (ETH/SOL transfer) (spec §5) --------------

def gate2_sealed(sealed_pairs: list[tuple[V3Trade, float]],
                 baseline_sealed: dict) -> dict:
    m = v3_metrics(sealed_pairs, EngineConfig())
    base_dd = baseline_sealed.get("max_dd_r", 0.0)
    passed = (m["n"] > 0 and m["cost_stress"]["net_r_3x"] > 0
              and abs(m["max_dd_r"]) <= abs(base_dd))
    return {"n": m["n"], "net_r_3x": m["cost_stress"]["net_r_3x"],
            "max_dd_r": m["max_dd_r"], "baseline_max_dd_r": base_dd,
            "passed": passed}


def _asset_leg(pairs: list[tuple[V3Trade, float]]) -> dict:
    m = v3_metrics(pairs, EngineConfig())
    return {"n": m["n"], "net_r_3x": m["cost_stress"]["net_r_3x"]}


def gate3_transfer(eth_pairs: list[tuple[V3Trade, float]],
                   sol_pairs: list[tuple[V3Trade, float]]) -> dict:
    eth = _asset_leg(eth_pairs)
    sol = _asset_leg(sol_pairs)
    passed = all(leg["n"] >= MIN_TRANSFER_TRADES and leg["net_r_3x"] > 0
                 for leg in (eth, sol))
    return {"eth": eth, "sol": sol, "passed": passed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_gate23.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_gate23.py
git diff --cached --stat
git commit -m "feat(v3-eval): Gate 2 sealed BTC + Gate 3 transfer"
```

---

### Task 10: Report builder — fit, gates, sealed protection, verdict

**Files:**
- Modify: `src/moonface/signal/engine/v3/evaluate.py` (append)
- Test: `tests/test_v3_eval_report.py`

**Interfaces:**
- Consumes: everything from Tasks 1–9; `engine_hash_v3`; `calibration.series_fingerprint`.
- Produces: `fitted_matrix_payload(fitted_matrix) -> dict` (JSON-safe); `build_eval_report(btc, eth, sol, cfg_v3, cfg_v22, warmup, lookback=LOOKBACK) -> dict` (`btc/eth/sol` are candle lists). Fits on BTC train; Gate 1 on BTC validation; Gates 2–3 only if Gate 1 passes; sealed/ETH/SOL untouched otherwise. Verdict is one of `VERDICTS`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_eval_report.py
"""Report assembly: sealed protection, verdict routing, JSON safety."""
import json

from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import VERDICTS, build_eval_report

from tests.helpers_v3 import uptrend

CFG3 = EngineConfigV3()
CFG22 = EngineConfig()


def test_report_structure_and_sealed_protection():
    # short synthetic series -> Gate 1 fails on the PANEL_FLOOR power floor,
    # so sealed/transfer must never be computed
    btc = uptrend(1200)
    report = build_eval_report(btc, uptrend(1200), uptrend(1200),
                               CFG3, CFG22, warmup=400, lookback=400)
    assert report["verdict"] in VERDICTS
    assert report["label"].startswith("v3 backtest evaluation")
    assert "fitted" in report and "gate1" in report
    if not report["gate1"]["passed"]:
        assert report["verdict"] == "CLOSED_NEGATIVE_VALIDATION"
        assert report["gate2"] is None and report["gate3"] is None
    json.dumps(report)  # must be JSON-serializable as-is


def test_fit_uses_only_btc_train(monkeypatch):
    import moonface.signal.engine.v3.evaluate as ev

    seen = {}
    real = ev.fit_q_floors

    def spy(train, cfg):
        seen["train"] = list(train)
        return real(train, cfg)

    monkeypatch.setattr(ev, "fit_q_floors", spy)
    ev.build_eval_report(uptrend(1200), uptrend(1200), uptrend(1200),
                         CFG3, CFG22, warmup=400, lookback=400)
    assert "train" in seen
    assert all(t.exit_ts_ms < ev.TRAIN_END_TS_MS for t in seen["train"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_eval_report.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_eval_report'`

- [ ] **Step 3: Append the implementation to evaluate.py**

```python
# --- report assembly (spec §6) ----------------------------------------------
from moonface.signal.engine.calibration import series_fingerprint  # noqa: E402
from moonface.signal.engine.v3.config_v3 import engine_hash_v3     # noqa: E402


def fitted_matrix_payload(fitted_matrix: dict) -> dict:
    return {f"{d.value}/{v.value}": name
            for (d, v), name in sorted(
                fitted_matrix.items(), key=lambda kv: str(kv[0]))}


def build_eval_report(btc: list[Candle], eth: list[Candle], sol: list[Candle],
                      cfg_v3: EngineConfigV3, cfg_v22: EngineConfig,
                      warmup: int, lookback: int = LOOKBACK) -> dict:
    """Single registered evaluation. Fit on BTC train; Gate 1 on BTC
    validation; Gates 2-3 for the survivor only. Sealed/ETH/SOL touched
    exclusively inside this gate flow."""
    # 1) fit on BTC TRAIN only (overlapping fit panel, segmented)
    fit_all = fit_panel(btc, cfg_v3, cfg_v22, lookback)
    fit_segs, _ = segment_v3(fit_all)
    train = fit_segs["train"]
    q_floors = fit_q_floors(train, cfg_v3)
    fitted_matrix = prune_cells(train)
    cfg_fit = fitted_cfg(cfg_v3, q_floors)

    # 2) BTC one-position stream (fitted), split into validation/sealed
    btc_pairs = v3_stream(btc, cfg_fit, fitted_matrix, cfg_v22, lookback)
    val_pairs = split_pairs_by_window(btc_pairs, TRAIN_END_TS_MS + PURGE_MS,
                                       SEALED_START_TS_MS)
    sealed_pairs = split_pairs_by_window(btc_pairs, SEALED_START_TS_MS + PURGE_MS,
                                         SPAN_END_TS_MS)

    # 3) v2.2 baselines: one full-series stream, split by window (warmup intact)
    base_pairs = v22_pairs(btc, cfg_v22, warmup)
    base_val = replay_metrics(
        split_pairs_by_window(base_pairs, TRAIN_END_TS_MS + PURGE_MS,
                              SEALED_START_TS_MS), cfg_v22)
    base_sealed = replay_metrics(
        split_pairs_by_window(base_pairs, SEALED_START_TS_MS + PURGE_MS,
                              SPAN_END_TS_MS), cfg_v22)

    # 4) gate flow with sealed protection
    gate1 = gate1_validation(val_pairs, base_val)
    gate2 = gate3 = None
    if not gate1["passed"]:
        verdict = "CLOSED_NEGATIVE_VALIDATION"
    else:
        gate2 = gate2_sealed(sealed_pairs, base_sealed)
        if not gate2["passed"]:
            verdict = "CLOSED_NEGATIVE_SEALED_BTC"
        else:
            eth_pairs = split_pairs_by_window(
                v3_stream(eth, cfg_fit, fitted_matrix, cfg_v22, lookback),
                SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS)
            sol_pairs = split_pairs_by_window(
                v3_stream(sol, cfg_fit, fitted_matrix, cfg_v22, lookback),
                SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS)
            gate3 = gate3_transfer(eth_pairs, sol_pairs)
            verdict = ("ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
                       if gate3["passed"] else "CLOSED_NEGATIVE_TRANSFER")

    return {
        "engine_hash_v3": engine_hash_v3(cfg_v3),
        "label": EVAL_LABEL,
        "data": {"btc_candles": len(btc), "eth_candles": len(eth),
                 "sol_candles": len(sol),
                 "btc_fingerprint": series_fingerprint(btc)},
        "frozen_constants": {
            "train_end_ts_ms": TRAIN_END_TS_MS,
            "sealed_start_ts_ms": SEALED_START_TS_MS,
            "purge_ms": PURGE_MS, "effective_trials": EFFECTIVE_TRIALS,
            "ci_lo_q": CI_LO_Q, "panel_floor": PANEL_FLOOR,
            "bracket": {"k_stop": K_STOP, "k_trail": K_TRAIL,
                        "max_bars": MAX_BARS, "atr_period": ATR_PERIOD}},
        "segments": {"train": len(train)},
        "fitted": {"q_floors": q_floors,
                   "matrix": fitted_matrix_payload(fitted_matrix),
                   "effective_trials": EFFECTIVE_TRIALS},
        "baseline_v22": {"validation": base_val, "sealed": base_sealed},
        "gate1": gate1, "gate2": gate2, "gate3": gate3,
        "verdict": verdict,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_eval_report.py -q`
Expected: 2 passed. The synthetic series are short, so Gate 1 fails on `PANEL_FLOOR`; the test asserts the sealed-protection branch, not a green verdict.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/evaluate.py tests/test_v3_eval_report.py
git diff --cached --stat
git commit -m "feat(v3-eval): report builder, sealed protection, verdict"
```

---

### Task 11: CLI + full-suite green + frozen pre-registration

**Files:**
- Create: `tools/v3_evaluate.py`
- Create: `experiments/engine/ENGINE_V3_EVAL_2026-07.md`
- Test: `tests/test_v3_evaluate_cli.py`

**Interfaces:**
- Consumes: `foundation.bundle.load_bundle`; `build_eval_report`; `EngineConfigV3`, `EngineConfig`; `ASSETS`.
- Produces: `run(argv, loaders=None) -> int` (injectable `loaders` dict `{"BTC"/"ETH"/"SOL": callable(asset, start, end, cache) -> object with .candles}` for hermetic tests; defaults to `load_bundle`); writes report JSON.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v3_evaluate_cli.py
"""CLI wiring with injectable loaders (hermetic — no network/bundle)."""
import json
import types

from moonface.signal.engine.v3.evaluate import VERDICTS
from tools.v3_evaluate import run

from tests.helpers_v3 import uptrend


def _loader_factory():
    def load(asset, start_ms, end_ms, cache_dir):
        return types.SimpleNamespace(candles=uptrend(1200))
    return {"BTC": load, "ETH": load, "SOL": load}


def test_cli_runs_and_writes_report(tmp_path):
    out = tmp_path / "rep.json"
    rc = run(["--start-ms", "0", "--end-ms", "1", "--warmup", "400",
              "--lookback", "400", "--out", str(out)],
             loaders=_loader_factory())
    assert rc == 0
    report = json.loads(out.read_text())
    assert report["verdict"] in VERDICTS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_v3_evaluate_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.v3_evaluate'`

- [ ] **Step 3: Write the CLI**

```python
# tools/v3_evaluate.py
"""Pre-registered, read-only backtest evaluation of the v3 engine.

Fits minimal v3 constants on BTC train, kills/selects on validation, confirms
once on the sealed year + ETH/SOL transfer — apples-to-apples vs frozen v2.2.
NEVER gates capital, NEVER edits the engine. A passing verdict authorizes a
HUMAN to re-freeze the fitted constants and start a small paper allocation.

Usage:
  .venv/bin/python -m tools.v3_evaluate \
      --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
      --out experiments/engine/v3_eval_2026-07.json
"""
from __future__ import annotations

import argparse
import json

from moonface.foundation.bundle import load_bundle
from moonface.signal.engine.config import EngineConfig, load_engine_config
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import ASSETS, build_eval_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="v3-evaluate")
    p.add_argument("--v22-engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000)
    p.add_argument("--lookback", type=int, default=400)
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None, loaders: dict | None = None) -> int:
    args = build_parser().parse_args(argv)
    load = loaders or {k: load_bundle for k in ASSETS}
    cfg_v22 = load_engine_config(args.v22_engine)
    cfg_v3 = EngineConfigV3()

    def candles(key: str):
        return load[key](ASSETS[key], args.start_ms, args.end_ms,
                         args.cache_dir).candles

    report = build_eval_report(candles("BTC"), candles("ETH"), candles("SOL"),
                               cfg_v3, cfg_v22, args.warmup, args.lookback)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_v3_evaluate_cli.py -q`
Expected: 1 passed

- [ ] **Step 5: Confirm the whole suite is green**

Run: `.venv/bin/pytest -q`
Expected: all pass, including v2.2 (`test_engine_config.py`, `test_engine_confluence.py`) and every `test_v3_*`.

- [ ] **Step 6: Print the pinned v3 hash for the registration**

Run: `.venv/bin/python -c "from moonface.signal.engine.v3.config_v3 import EngineConfigV3, engine_hash_v3; print(engine_hash_v3(EngineConfigV3()))"`
Expected: a 64-char hex string. Copy it into the doc below in place of `<PASTE_HASH>`.

- [ ] **Step 7: Write the frozen pre-registration**

```markdown
# Engine v3 — Backtest Evaluation — Pre-Registration (FROZEN)

**Instrument:** `tools/v3_evaluate.py` / `src/moonface/signal/engine/v3/evaluate.py`.
Spec: `docs/research-log/specs/2026-07-06-v3-eval-instrument-design.md`.
**Pinned `engine_hash_v3(EngineConfigV3())`:** `<PASTE_HASH>`
**Registered:** 2026-07-06. Read-only; never gates capital.

## Frozen splits (BTC/ETH/SOL 1h, purge = 168h)
- Train: 2020-01-01 → 2024-01-01 (fit q_floors + prune cells)
- Validation: 2024-01-01 → 2025-07-01 (select / DSR / kill)
- Sealed: 2025-07-01 → 2026-07-01 (one look; BTC + ETH/SOL)

## Fit (Minimal)
Isotonic per-mechanism q_floors + negative/underpowered cell pruning ONLY;
trigger params and the v2.2 ATR bracket (2.0/3.0/96/14) stay frozen.
Effective trials T = 12.

## Gate (all required)
1. Validation: net-R > 0 @ 3x cost; family-corrected block-CI lower bound > 0
   (CI_LO_Q = 0.05/12/2); max-drawdown-R <= v2.2; n >= 200.
2. Sealed BTC: net-R sign > 0 @ 3x cost; max-drawdown-R <= v2.2 sealed.
3. Transfer: net-R sign > 0 @ 3x cost on BOTH ETH and SOL (>= 20 trades each),
   fitted-BTC constants applied unchanged.

Verdict: CLOSED_NEGATIVE_VALIDATION / _SEALED_BTC / _TRANSFER, or
ALL_GATES_PASSED_HUMAN_DECISION_PENDING.

## Discipline
One registered run; re-runs only for demonstrated mechanical failure. Sealed
touched only inside the gate flow, only if Gate 1 passes. A passing verdict
authorizes a HUMAN to re-freeze the fitted constants as a live candidate and
start a small paper allocation — it is not itself a deployment, and not a
substitute for the forward-paper registration.
```

- [ ] **Step 8: Commit**

```bash
git add tools/v3_evaluate.py tests/test_v3_evaluate_cli.py experiments/engine/ENGINE_V3_EVAL_2026-07.md
git diff --cached --stat
git commit -m "feat(v3-eval): CLI, injectable loaders, frozen pre-registration"
```

---

## Notes for the implementer

- Tasks are strictly ordered; each appends to the single `evaluate.py`.
- The `# noqa: E402` mid-file imports are intentional — appending imports per
  task keeps each task self-contained; a final cleanup pass may hoist them to
  the top, but do not reorder in a way that breaks the append-only task flow.
- Synthetic series in tests are short, so gates fail on the power floor — the
  tests assert *routing/structure/sealed-protection*, never a green verdict. A
  green verdict only comes from the registered run over real BTC/ETH/SOL.
- `load_engine_config("promotion/engine.json")` returns disabled v2.2 defaults
  if the file is absent — that is correct; the bracket/baseline only need the
  frozen exit + module constants, not the `enabled` flag.
- The registered run is a single `tools.v3_evaluate` invocation over the full
  span; expect minutes, not seconds (three assets × one-position streams).
