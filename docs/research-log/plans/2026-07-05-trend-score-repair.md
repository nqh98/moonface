# Trend-Score Repair Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pre-registered evaluation lane that tests exactly 3 audit-licensed trend-book scoring repairs (tier merge, side/vol-conditional tiering, isotonic calibration) through a 3-gate promotion bar, producing at most one v2.3-licensed candidate.

**Architecture:** One new analysis module `src/moonface/signal/engine/repair.py` (read-only, additive; same precedent as `audit.py`), one CLI `tools/engine_repair.py` (mirrors `tools/engine_audit.py`), one frozen pre-registration doc, and a conditional forward-shadow CLI built only if a survivor emerges. All panel machinery is reused from `calibration.py`; all bootstrap machinery follows `audit.py`.

**Tech Stack:** Python 3.11+, stdlib only (no numpy). Tests via pytest in `tests/`. Spec: `docs/research-log/specs/2026-07-05-trend-score-repair-design.md`.

## Global Constraints

- **Engine untouched.** No edits to any existing file under `src/moonface/signal/engine/` — `repair.py` is a NEW file only. v2.2 hash `b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5` must stay pinned (existing tests `test_engine_config.py`, `test_engine_calibration_pass.py` must stay green).
- **Stdlib only.** No numpy. Bootstrap randomness via `random.Random(seed)`.
- **Run commands:** `.venv/bin/pytest …` and `.venv/bin/python -m tools.engine_repair …`. Never bare `python`, never `rtk python`.
- **Git:** no AI attribution trailers (no `Co-Authored-By`). Never chain `git add && git commit` blindly — stage, check `git diff --cached --stat`, then commit. `docs/` is globally gitignored; plan/spec files are already committed, do not re-add.
- **Frozen analysis constants (from the spec — copy verbatim, tested in Task 1):** `TRAIN_END_TS_MS = 1688169600000` (2023-07-01T00:00:00Z), `SEALED_START_TS_MS = 1748736000000` (2025-06-01T00:00:00Z), `PURGE_MS = 168 * 3_600_000`, family alpha 0.05 Bonferroni over 3 candidates → CI quantiles `0.05/3/2 = 0.008333…` and `1 − 0.008333…`, offset grid `(0, 5, 10, 15, 20)`, cell floor 30, monotonicity bucket floor 30. Panel floor is `calibration.PANEL_FLOOR` (200).
- **Registered run window (same as the audit's registered run):** `--start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000`. One registered run; re-runs only for demonstrated mechanical failure.
- **TDD:** every task writes its failing test first, verifies failure, implements, verifies pass, commits.
- Sealed-window discipline: nothing in any task may evaluate any candidate on the sealed segment except through `build_repair_report`'s gate flow.

---

### Task 1: Frozen constants + chronological segmentation

**Files:**
- Create: `src/moonface/signal/engine/repair.py`
- Create: `tests/helpers_repair.py`
- Test: `tests/test_engine_repair_splits.py`

**Interfaces:**
- Consumes: `HypoTrade` from `moonface.signal.engine.calibration`.
- Produces: module constants `TRAIN_END_TS_MS: int`, `SEALED_START_TS_MS: int`, `PURGE_MS: int`, `FAMILY_ALPHA: float`, `N_CANDIDATES: int`, `CI_LO_Q: float`, `CI_HI_Q: float`, `OFFSET_GRID: tuple[int, ...]`, `CELL_FLOOR: int`, `MONO_BUCKET_FLOOR: int`, `CANDIDATES: tuple[str, str, str]`, `REPAIR_LABEL: str`; function `segment_panel(panel, train_end_ts_ms=..., sealed_start_ts_ms=..., purge_ms=...) -> tuple[dict[str, list[HypoTrade]], int]` returning `{"train": [...], "validation": [...], "sealed": [...]}` plus a dropped count.

- [ ] **Step 1: Write the shared test helper**

```python
# tests/helpers_repair.py
"""Shared synthetic fixtures for the trend-score-repair tests (hermetic)."""
from __future__ import annotations

from moonface.signal.engine.calibration import HypoTrade

H = 3_600_000


def ht(i: int, score: int, net_r: float, direction: int = 1,
       vol: str = "normal") -> HypoTrade:
    return HypoTrade(
        entry_index=i, exit_index=i + 5, entry_ts_ms=i * H,
        exit_ts_ms=(i + 5) * H, book="trend", direction=direction,
        score=score, breadth=3, policy="ALLOW", macro_effective="NEUTRAL",
        vol_state=vol, net_r=net_r, bars_held=5, exit_reason="target")
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_engine_repair_splits.py
"""Frozen constants and leakage-safe chronological segmentation."""
from moonface.signal.engine.repair import (
    CI_HI_Q,
    CI_LO_Q,
    FAMILY_ALPHA,
    N_CANDIDATES,
    PURGE_MS,
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    segment_panel,
)

from tests.helpers_repair import H, ht


def test_frozen_boundaries():
    assert TRAIN_END_TS_MS == 1688169600000      # 2023-07-01T00:00:00Z
    assert SEALED_START_TS_MS == 1748736000000   # 2025-06-01T00:00:00Z
    assert PURGE_MS == 168 * H
    assert FAMILY_ALPHA == 0.05 and N_CANDIDATES == 3
    assert abs(CI_LO_Q - 0.05 / 3 / 2) < 1e-12
    assert abs(CI_HI_Q - (1.0 - 0.05 / 3 / 2)) < 1e-12


def test_segment_panel_boundaries():
    train_end = 1000 * H
    sealed_start = 2000 * H
    trades = [
        ht(10, 70, 0.5),     # exit 15H < train_end -> train
        ht(1100, 70, 0.5),   # entry >= train_end + purge, exit < sealed -> validation
        ht(1001, 70, 0.5),   # entry inside the purge window -> dropped
        ht(2200, 70, 0.5),   # entry >= sealed_start + purge -> sealed
        ht(2001, 70, 0.5),   # entry inside the sealed purge window -> dropped
    ]
    segs, dropped = segment_panel(trades, train_end, sealed_start)
    assert [t.entry_index for t in segs["train"]] == [10]
    assert [t.entry_index for t in segs["validation"]] == [1100]
    assert [t.entry_index for t in segs["sealed"]] == [2200]
    assert dropped == 2


def test_trade_spanning_train_boundary_is_dropped():
    # entry 995H (< train_end), exit 1000H (not < train_end): belongs nowhere
    segs, dropped = segment_panel([ht(995, 70, 0.5)], 1000 * H, 2000 * H)
    assert dropped == 1
    assert not segs["train"] and not segs["validation"] and not segs["sealed"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_splits.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.repair'`

- [ ] **Step 4: Write the implementation**

```python
# src/moonface/signal/engine/repair.py
"""Pre-registered trend-score repair lane for the frozen v2.2 engine.

Evaluates exactly three audit-licensed candidate scoring repairs of the TREND
book through a three-gate promotion bar (validation ordering, sealed window,
replay confirm). Read-only: never gates capital, never mutates the engine,
never changes a frozen constant. Any promotion is a human decision (v2.3 =
new ENGINE_VERSION + new hash + new registration + fresh clock).

Spec: docs/research-log/specs/2026-07-05-trend-score-repair-design.md
Pre-reg: experiments/engine/TREND_SCORE_REPAIR_2026-07.md
"""
from __future__ import annotations

import random

from moonface.foundation.models import Candle
from moonface.foundation.risk import atr
from moonface.signal.engine.calibration import (
    BLOCK_BARS,
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    BUCKET_EDGES,
    PANEL_FLOOR,
    BarRow,
    HypoTrade,
    overlapping_panel,
    scoring_pass,
    series_fingerprint,
    simulate_entry,
    spearman,
)
from moonface.signal.engine.config import EngineConfig, engine_hash
from moonface.signal.engine.confluence import BASE_THRESHOLD, BREADTH_MIN
from moonface.signal.engine.honesty import cost_stress

# --- frozen split + inference constants (spec section 2 and 4) --------------
TRAIN_END_TS_MS = 1688169600000      # 2023-07-01T00:00:00Z
SEALED_START_TS_MS = 1748736000000   # 2025-06-01T00:00:00Z
PURGE_MS = BLOCK_BARS * 3_600_000    # 168 one-hour bars

FAMILY_ALPHA = 0.05
N_CANDIDATES = 3
CI_LO_Q = FAMILY_ALPHA / N_CANDIDATES / 2.0
CI_HI_Q = 1.0 - CI_LO_Q

OFFSET_GRID = (0, 5, 10, 15, 20)
CELL_FLOOR = 30
MONO_BUCKET_FLOOR = 30

CANDIDATES = ("c1_tier_merge", "c2_side_vol", "c3_isotonic")

REPAIR_LABEL = (
    "trend-score repair — pre-registered; read-only; "
    "no live constant changes; promotion is a human decision"
)


def segment_panel(panel: list[HypoTrade],
                  train_end_ts_ms: int = TRAIN_END_TS_MS,
                  sealed_start_ts_ms: int = SEALED_START_TS_MS,
                  purge_ms: int = PURGE_MS,
                  ) -> tuple[dict[str, list[HypoTrade]], int]:
    """Leakage-safe chronological segments. A trade must fall entirely inside
    a segment (train requires the EXIT before the boundary; later segments
    require the ENTRY after boundary + purge); everything else is dropped."""
    segs: dict[str, list[HypoTrade]] = {
        "train": [], "validation": [], "sealed": []}
    dropped = 0
    for t in panel:
        if t.exit_ts_ms < train_end_ts_ms:
            segs["train"].append(t)
        elif (t.entry_ts_ms >= train_end_ts_ms + purge_ms
              and t.exit_ts_ms < sealed_start_ts_ms):
            segs["validation"].append(t)
        elif t.entry_ts_ms >= sealed_start_ts_ms + purge_ms:
            segs["sealed"].append(t)
        else:
            dropped += 1
    return segs, dropped
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_splits.py -q`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/helpers_repair.py tests/test_engine_repair_splits.py
git diff --cached --stat
git commit -m "feat(repair): frozen split constants + leakage-safe segmentation"
```

---

### Task 2: Candidate C1 — monotone tier merge (PAVA over frozen buckets)

**Files:**
- Modify: `src/moonface/signal/engine/repair.py` (append)
- Test: `tests/test_engine_repair_c1.py`

**Interfaces:**
- Consumes: `BUCKET_EDGES` (== `(40, 60, 75)`) from calibration; `HypoTrade`.
- Produces: `_pava_blocks(means: list[float], weights: list[float]) -> list[list[float]]` (each block `[mean, weight, size]`; shared with C3), `fit_tier_merge(train: list[HypoTrade]) -> tuple[int, ...]` (kept interior edges), `apply_tier_merge(score: int, kept_edges: tuple[int, ...]) -> int` (0-based merged bucket index), `c1_entry_threshold(kept_edges: tuple[int, ...]) -> int`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_c1.py
"""C1 tier repair: pool-adjacent-violators over the frozen score buckets."""
from moonface.signal.engine.repair import (
    apply_tier_merge,
    c1_entry_threshold,
    fit_tier_merge,
)

from tests.helpers_repair import ht


def _bucket_trades(spec):
    """spec: list of (score, mean_net_r, n)."""
    out = []
    i = 0
    for score, mean, n in spec:
        for _ in range(n):
            out.append(ht(i, score, mean))
            i += 10
    return out


def test_identity_when_bucket_means_monotone():
    train = _bucket_trades(
        [(20, -0.2, 10), (50, -0.1, 10), (65, 0.1, 10), (80, 0.3, 10)])
    assert fit_tier_merge(train) == (40, 60, 75)


def test_inverted_top_bucket_merges_into_tier_b():
    train = _bucket_trades(
        [(20, -0.2, 10), (50, -0.1, 10), (65, 0.3, 10), (80, 0.0, 10)])
    assert fit_tier_merge(train) == (40, 60)


def test_empty_bucket_merges_left():
    # [40,60) has no trades: it is absorbed leftward before PAVA
    train = _bucket_trades([(20, -0.2, 10), (65, 0.1, 10), (80, 0.3, 10)])
    assert fit_tier_merge(train) == (60, 75)


def test_underpowered_input_returns_identity():
    assert fit_tier_merge([]) == (40, 60, 75)
    assert fit_tier_merge(_bucket_trades([(65, 0.1, 5)])) == (40, 60, 75)


def test_apply_and_entry_threshold():
    edges = (40, 60)
    assert apply_tier_merge(30, edges) == 0
    assert apply_tier_merge(45, edges) == 1
    assert apply_tier_merge(60, edges) == 2
    assert apply_tier_merge(90, edges) == 2
    assert c1_entry_threshold((40, 60)) == 60
    assert c1_entry_threshold((40, 60, 75)) == 60
    assert c1_entry_threshold((40,)) == 40
    assert c1_entry_threshold(()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_c1.py -q`
Expected: FAIL with `ImportError: cannot import name 'apply_tier_merge'`

- [ ] **Step 3: Append the implementation to repair.py**

```python
# --- Candidate C1: monotone tier merge (spec section 3, finding: Tier-A
# inversion at n=36) ----------------------------------------------------------
_C1_BOUNDS = ((0, 40), (40, 60), (60, 75), (75, 10 ** 9))


def _pava_blocks(means: list[float], weights: list[float]) -> list[list[float]]:
    """Weighted pool-adjacent-violators; returns [mean, weight, size] blocks
    with weakly increasing means."""
    blocks: list[list[float]] = []
    for mean, weight in zip(means, weights):
        blocks.append([mean, weight, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            m2, w2, s2 = blocks.pop()
            m1, w1, s1 = blocks.pop()
            tw = w1 + w2
            merged = (m1 * w1 + m2 * w2) / tw if tw > 0 else 0.0
            blocks.append([merged, tw, s1 + s2])
    return blocks


def fit_tier_merge(train: list[HypoTrade]) -> tuple[int, ...]:
    """Kept interior edges after PAVA over the frozen buckets. Empty buckets
    merge left (a leading empty bucket merges right). Fewer than two populated
    buckets -> identity (the candidate degrades to a no-op)."""
    means: list[float] = []
    weights: list[float] = []
    sizes: list[int] = []
    carry = 0
    for lo, hi in _C1_BOUNDS:
        rs = [t.net_r for t in train if lo <= t.score < hi]
        if not rs:
            if sizes:
                sizes[-1] += 1
            else:
                carry += 1
            continue
        means.append(sum(rs) / len(rs))
        weights.append(float(len(rs)))
        sizes.append(1 + carry)
        carry = 0
    if len(means) < 2:
        return BUCKET_EDGES
    blocks = _pava_blocks(means, weights)
    kept: list[int] = []
    cum_elems = 0
    for _, _, block_size in blocks[:-1]:
        cum_elems += int(block_size)
        cum_orig = sum(sizes[:cum_elems])
        kept.append(BUCKET_EDGES[cum_orig - 1])
    return tuple(kept)


def apply_tier_merge(score: int, kept_edges: tuple[int, ...]) -> int:
    return sum(1 for edge in kept_edges if score >= edge)


def c1_entry_threshold(kept_edges: tuple[int, ...]) -> int:
    """Lower edge of the merged bucket containing the frozen BASE_THRESHOLD."""
    return max((e for e in kept_edges if e <= BASE_THRESHOLD), default=0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_c1.py tests/test_engine_repair_splits.py -q`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/test_engine_repair_c1.py
git diff --cached --stat
git commit -m "feat(repair): C1 monotone tier merge via weighted PAVA"
```

---

### Task 3: Candidate C2 — side/vol-conditional threshold offsets

**Files:**
- Modify: `src/moonface/signal/engine/repair.py` (append)
- Test: `tests/test_engine_repair_c2.py`

**Interfaces:**
- Consumes: `OFFSET_GRID`, `CELL_FLOOR`, `BASE_THRESHOLD`, `HypoTrade`.
- Produces: `_C2_CELLS: tuple[tuple[str, str], ...]`, `fit_side_vol_offsets(train: list[HypoTrade]) -> dict[tuple[str, str], int]`, `apply_side_vol_offset(trade: HypoTrade, offsets: dict[tuple[str, str], int]) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_c2.py
"""C2 conditional tiering: per-(side, vol) threshold offsets, Train-derived."""
from moonface.signal.engine.repair import (
    apply_side_vol_offset,
    fit_side_vol_offsets,
)

from tests.helpers_repair import ht


def _uniform_cells(mean):
    train = []
    i = 0
    for side in (1, -1):
        for vol in ("normal", "high"):
            for _ in range(40):
                train.append(ht(i, 70, mean, direction=side, vol=vol))
                i += 10
    return train


def test_offsets_zero_when_every_cell_matches_pool():
    offs = fit_side_vol_offsets(_uniform_cells(0.1))
    assert set(offs) == {("LONG", "normal"), ("LONG", "high"),
                         ("SHORT", "normal"), ("SHORT", "high")}
    assert all(v == 0 for v in offs.values())


def test_bad_cell_gets_max_offset_when_no_offset_cures_it():
    train = []
    i = 0
    for _ in range(40):
        train.append(ht(i, 70, 0.3))                      # LONG normal: good
        i += 10
    for _ in range(40):
        train.append(ht(i, 70, -0.3, direction=-1))       # SHORT normal: bad
        i += 10
    offs = fit_side_vol_offsets(train)
    assert offs[("LONG", "normal")] == 0
    # every offset either leaves the bad mean below pool or empties the cell
    assert offs[("SHORT", "normal")] == 20
    # cells with no Train data are conservative: max offset
    assert offs[("LONG", "high")] == 20


def test_all_zero_when_pooled_qualifiers_underpowered():
    train = [ht(i * 10, 70, 0.1) for i in range(10)]      # 10 < CELL_FLOOR
    assert all(v == 0 for v in fit_side_vol_offsets(train).values())


def test_apply_side_vol_offset():
    offs = {("LONG", "normal"): 0, ("SHORT", "normal"): 20}
    assert apply_side_vol_offset(ht(0, 70, 0.0), offs) == 70.0
    assert apply_side_vol_offset(ht(0, 70, 0.0, direction=-1), offs) == 50.0
    # missing cell -> offset 0
    assert apply_side_vol_offset(ht(0, 70, 0.0, vol="high"), offs) == 70.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_c2.py -q`
Expected: FAIL with `ImportError: cannot import name 'apply_side_vol_offset'`

- [ ] **Step 3: Append the implementation to repair.py**

```python
# --- Candidate C2: side/vol-conditional tiering (spec section 3, finding:
# ordering concentrated in LONG + high-vol) -----------------------------------
_C2_CELLS = (("LONG", "normal"), ("LONG", "high"),
             ("SHORT", "normal"), ("SHORT", "high"))


def fit_side_vol_offsets(train: list[HypoTrade],
                         ) -> dict[tuple[str, str], int]:
    """Per-cell threshold offset: the smallest grid offset at which the cell's
    qualifying mean net R reaches the pooled qualifying mean. Cells that never
    reach CELL_FLOOR qualifying trades stay at the max offset (conservative).
    If the pooled qualifying set itself is underpowered, every offset is 0
    (the candidate degrades to a no-op)."""
    pooled_rs = [t.net_r for t in train if t.score >= BASE_THRESHOLD]
    if len(pooled_rs) < CELL_FLOOR:
        return {cell: 0 for cell in _C2_CELLS}
    pooled_mean = sum(pooled_rs) / len(pooled_rs)
    out: dict[tuple[str, str], int] = {}
    for side, vol in _C2_CELLS:
        want = 1 if side == "LONG" else -1
        cell = [t for t in train
                if t.direction == want and t.vol_state == vol]
        chosen = OFFSET_GRID[-1]
        for off in OFFSET_GRID:
            rs = [t.net_r for t in cell if t.score >= BASE_THRESHOLD + off]
            if len(rs) < CELL_FLOOR:
                continue
            if sum(rs) / len(rs) >= pooled_mean:
                chosen = off
                break
        out[(side, vol)] = chosen
    return out


def apply_side_vol_offset(trade: HypoTrade,
                          offsets: dict[tuple[str, str], int]) -> float:
    side = "LONG" if trade.direction > 0 else "SHORT"
    return float(trade.score - offsets.get((side, trade.vol_state), 0))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_c2.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/test_engine_repair_c2.py
git diff --cached --stat
git commit -m "feat(repair): C2 side/vol-conditional threshold offsets"
```

---

### Task 4: Candidate C3 — isotonic score→E[R] calibration

**Files:**
- Modify: `src/moonface/signal/engine/repair.py` (append)
- Test: `tests/test_engine_repair_c3.py`

**Interfaces:**
- Consumes: `_pava_blocks` from Task 2; `HypoTrade`.
- Produces: `fit_isotonic(train: list[HypoTrade]) -> tuple[tuple[int, float], ...]` (ascending `(score, fitted_mean)` pairs), `apply_isotonic(score: int, curve: tuple[tuple[int, float], ...]) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_c3.py
"""C3 monotone calibration: isotonic regression of net R on score."""
from moonface.signal.engine.repair import apply_isotonic, fit_isotonic

from tests.helpers_repair import ht


def test_fit_is_monotone_and_pools_violations():
    train = ([ht(i, 40, -0.2) for i in range(0, 300, 10)]
             + [ht(i, 60, 0.3) for i in range(300, 600, 10)]
             + [ht(i, 80, 0.1) for i in range(600, 900, 10)])
    curve = fit_isotonic(train)
    assert [s for s, _ in curve] == [40, 60, 80]
    vals = [v for _, v in curve]
    assert vals == sorted(vals)
    assert abs(vals[0] - (-0.2)) < 1e-9
    # 60 (0.3, n=30) and 80 (0.1, n=30) violate -> pooled to 0.2
    assert abs(vals[1] - 0.2) < 1e-9 and abs(vals[2] - 0.2) < 1e-9


def test_apply_is_a_right_continuous_step_lookup():
    curve = ((40, -0.2), (60, 0.2), (80, 0.2))
    assert apply_isotonic(30, curve) == -0.2   # below min -> first value
    assert apply_isotonic(40, curve) == -0.2
    assert apply_isotonic(59, curve) == -0.2
    assert apply_isotonic(60, curve) == 0.2
    assert apply_isotonic(95, curve) == 0.2


def test_empty_inputs():
    assert fit_isotonic([]) == ()
    assert apply_isotonic(70, ()) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_c3.py -q`
Expected: FAIL with `ImportError: cannot import name 'apply_isotonic'`

- [ ] **Step 3: Append the implementation to repair.py**

```python
# --- Candidate C3: isotonic score->E[R] calibration (spec section 3) ---------

def fit_isotonic(train: list[HypoTrade]) -> tuple[tuple[int, float], ...]:
    """Weighted isotonic regression of net R on the integer score, via PAVA
    over per-score means. Returns ascending (score, fitted_value) pairs."""
    by_score: dict[int, list[float]] = {}
    for t in train:
        by_score.setdefault(t.score, []).append(t.net_r)
    scores = sorted(by_score)
    if not scores:
        return ()
    means = [sum(by_score[s]) / len(by_score[s]) for s in scores]
    weights = [float(len(by_score[s])) for s in scores]
    blocks = _pava_blocks(means, weights)
    out: list[tuple[int, float]] = []
    i = 0
    for mean, _, size in blocks:
        for _ in range(int(size)):
            out.append((scores[i], round(mean, 6)))
            i += 1
    return tuple(out)


def apply_isotonic(score: int,
                   curve: tuple[tuple[int, float], ...]) -> float:
    """Step lookup: value of the largest curve score <= score; below the
    curve's minimum -> the first value; empty curve -> 0.0."""
    if not curve:
        return 0.0
    value = curve[0][1]
    for s, v in curve:
        if s <= score:
            value = v
        else:
            break
    return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_c3.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/test_engine_repair_c3.py
git diff --cached --stat
git commit -m "feat(repair): C3 isotonic score->E[R] calibration"
```

---

### Task 5: Candidate dispatch + Gate-1/Gate-2 ordering statistics

**Files:**
- Modify: `src/moonface/signal/engine/repair.py` (append)
- Test: `tests/test_engine_repair_stats.py`

**Interfaces:**
- Consumes: Tasks 2–4 fit/apply functions; `spearman`, `PANEL_FLOOR` from calibration.
- Produces: `candidate_value(name: str, fitted, score: int, direction: int, vol_state: str) -> float`, `score_trade(name: str, fitted, trade: HypoTrade) -> float`, `block_ci_q(items, key_fn, stat_fn, lo_q, hi_q, block_bars=..., draws=..., seed=...) -> tuple[float, float] | None`, `train_quartile_edges(values: list[float]) -> tuple[float, float, float]`, `monotone_by_edges(trades, name, fitted, edges, floor=MONO_BUCKET_FLOOR) -> dict`, `gate1_candidate(name, fitted, train, validation) -> dict`, `gate2_candidate(name, fitted, train, sealed) -> dict`. Gate dicts carry keys `n`, `delta_rho`, `delta_ci` (Gate 1 only), `monotonicity`, `passed`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_stats.py
"""Dispatch, generalized block CI, and the Gate-1/Gate-2 ordering criteria."""
import pytest

from moonface.signal.engine.audit import block_ci
from moonface.signal.engine.repair import (
    CI_HI_Q,
    CI_LO_Q,
    block_ci_q,
    gate1_candidate,
    gate2_candidate,
    monotone_by_edges,
    score_trade,
    train_quartile_edges,
)

from tests.helpers_repair import ht

_ITEMS = [(i, float(i % 7)) for i in range(0, 3360)]


def _key(pair):
    return pair[0]


def _mean(sample):
    return sum(v for _, v in sample) / len(sample)


def test_block_ci_q_generalizes_the_audit_ci():
    assert block_ci_q(_ITEMS, _key, _mean, 0.025, 0.975) == \
        block_ci(_ITEMS, _key, _mean)


def test_family_corrected_ci_is_wider_than_95():
    lo95, hi95 = block_ci_q(_ITEMS, _key, _mean, 0.025, 0.975)
    lo_c, hi_c = block_ci_q(_ITEMS, _key, _mean, CI_LO_Q, CI_HI_Q)
    assert lo_c <= lo95 and hi_c >= hi95


def test_score_trade_dispatch():
    t = ht(0, 70, 0.1)
    assert score_trade("c1_tier_merge", (40, 60), t) == 2.0
    assert score_trade("c2_side_vol", {("LONG", "normal"): 5}, t) == 65.0
    assert score_trade("c3_isotonic", ((40, -0.1), (70, 0.2)), t) == 0.2
    with pytest.raises(ValueError):
        score_trade("bogus", None, t)


def test_train_quartile_edges_and_monotone_buckets():
    values = [float(v) for v in range(1, 101)]
    q1, q2, q3 = train_quartile_edges(values)
    assert (q1, q2, q3) == (25.0, 50.0, 75.0)
    # 200 trades, candidate = identity c1 over untouched edges: score IS the
    # bucket driver; low bucket bad, high bucket good -> monotone
    trades = ([ht(i * 200, 45, -0.2) for i in range(100)]
              + [ht((100 + i) * 200, 80, 0.2) for i in range(100)])
    mono = monotone_by_edges(trades, "c1_tier_merge", (40, 60, 75),
                             (1.0, 2.0, 3.0))
    assert mono["monotone"] is True
    bad = ([ht(i * 200, 45, 0.2) for i in range(100)]
           + [ht((100 + i) * 200, 80, -0.2) for i in range(100)])
    mono_bad = monotone_by_edges(bad, "c1_tier_merge", (40, 60, 75),
                                 (1.0, 2.0, 3.0))
    assert mono_bad["monotone"] is False


def _gate_panel(n_blocks=70):
    """Each 168-bar block holds one (bad-low, good-mid, bad-top) trio, so the
    block bootstrap resamples i.i.d. trios: base rho ~ 0, C1-merged rho > 0."""
    trades = []
    for b in range(n_blocks):
        base_i = b * 1008              # 6 whole blocks apart; trio same block
        trades.append(ht(base_i, 45, -0.4))
        trades.append(ht(base_i + 10, 65, 0.4 + 0.001 * b))
        trades.append(ht(base_i + 20, 80, -0.4 + 0.001 * b))
    return trades


def test_gate1_passes_repairing_candidate_and_fails_identity():
    panel = _gate_panel()              # 210 trades >= PANEL_FLOOR
    good = gate1_candidate("c1_tier_merge", (40, 60), panel, panel)
    assert good["passed"] is True
    assert good["delta_rho"] > 0
    identity = gate1_candidate("c1_tier_merge", (40, 60, 75), panel, panel)
    assert identity["passed"] is False


def test_gate2_point_sign_rule():
    panel = _gate_panel()
    good = gate2_candidate("c1_tier_merge", (40, 60), panel, panel)
    assert good["passed"] is True
    identity = gate2_candidate("c1_tier_merge", (40, 60, 75), panel, panel)
    assert identity["passed"] is False   # delta exactly 0 is not > 0


def test_gates_fail_below_panel_floor():
    small = _gate_panel(n_blocks=10)     # 30 trades < PANEL_FLOOR
    assert gate1_candidate("c1_tier_merge", (40, 60),
                           small, small)["passed"] is False
    assert gate2_candidate("c1_tier_merge", (40, 60),
                           small, small)["passed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_stats.py -q`
Expected: FAIL with `ImportError: cannot import name 'block_ci_q'`

- [ ] **Step 3: Append the implementation to repair.py**

```python
# --- candidate dispatch ------------------------------------------------------

def candidate_value(name: str, fitted, score: int, direction: int,
                    vol_state: str) -> float:
    if name == "c1_tier_merge":
        return float(apply_tier_merge(score, fitted))
    if name == "c2_side_vol":
        side = "LONG" if direction > 0 else "SHORT"
        return float(score - fitted.get((side, vol_state), 0))
    if name == "c3_isotonic":
        return apply_isotonic(score, fitted)
    raise ValueError(f"unknown candidate: {name}")


def score_trade(name: str, fitted, trade: HypoTrade) -> float:
    return candidate_value(name, fitted, trade.score, trade.direction,
                           trade.vol_state)


# --- inference machinery (spec section 4) ------------------------------------

def block_ci_q(items: list, key_fn, stat_fn, lo_q: float, hi_q: float,
               block_bars: int = BLOCK_BARS, draws: int = BOOTSTRAP_DRAWS,
               seed: int = BOOTSTRAP_SEED) -> tuple[float, float] | None:
    """audit.block_ci generalized to arbitrary quantiles (family correction)."""
    blocks: dict[int, list] = {}
    for item in items:
        blocks.setdefault(key_fn(item) // block_bars, []).append(item)
    keys = sorted(blocks)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(draws):
        sample: list = []
        for _ in range(len(keys)):
            sample.extend(blocks[keys[rng.randrange(len(keys))]])
        stat = stat_fn(sample)
        if stat is not None:
            stats.append(stat)
    if len(stats) < draws // 2:
        return None
    stats.sort()
    return (stats[int(lo_q * (len(stats) - 1))],
            stats[int(hi_q * (len(stats) - 1))])


def _delta_stat(name: str, fitted):
    """Paired Delta-rho: candidate ordering minus frozen v2.2 ordering on the
    identical sample."""
    def stat(sample: list[HypoTrade]) -> float | None:
        cand = spearman([score_trade(name, fitted, t) for t in sample],
                        [t.net_r for t in sample])
        base = spearman([float(t.score) for t in sample],
                        [t.net_r for t in sample])
        if cand is None or base is None:
            return None
        return cand - base
    return stat


def train_quartile_edges(values: list[float]) -> tuple[float, float, float]:
    v = sorted(values)
    n = len(v)
    if n < 4:
        return (0.0, 0.0, 0.0)
    return (v[int(0.25 * (n - 1))], v[int(0.5 * (n - 1))],
            v[int(0.75 * (n - 1))])


def monotone_by_edges(trades: list[HypoTrade], name: str, fitted,
                      edges: tuple[float, float, float],
                      floor: int = MONO_BUCKET_FLOOR) -> dict:
    """Bucket mean net R by TRAIN-derived candidate-score quartiles; require
    weakly increasing means over buckets meeting the floor."""
    q1, q2, q3 = edges
    bounds = ((None, q1), (q1, q2), (q2, q3), (q3, None))
    buckets = []
    for lo, hi in bounds:
        rs = []
        for t in trades:
            s = score_trade(name, fitted, t)
            if (lo is None or s >= lo) and (hi is None or s < hi):
                rs.append(t.net_r)
        buckets.append({
            "lo": lo, "hi": hi, "n": len(rs),
            "mean_net_r": round(sum(rs) / len(rs), 4) if rs else None,
        })
    means = [b["mean_net_r"] for b in buckets
             if b["n"] >= floor and b["mean_net_r"] is not None]
    return {"buckets": buckets,
            "monotone": all(b >= a for a, b in zip(means, means[1:]))}


def gate1_candidate(name: str, fitted, train: list[HypoTrade],
                    validation: list[HypoTrade]) -> dict:
    """Family-corrected CI-clean Delta-rho > 0 AND monotone buckets."""
    stat = _delta_stat(name, fitted)
    delta = stat(validation)
    ci = block_ci_q(validation, lambda t: t.entry_index, stat,
                    CI_LO_Q, CI_HI_Q)
    edges = train_quartile_edges(
        [score_trade(name, fitted, t) for t in train])
    mono = monotone_by_edges(validation, name, fitted, edges)
    passed = (len(validation) >= PANEL_FLOOR and delta is not None
              and ci is not None and ci[0] > 0 and mono["monotone"])
    return {"n": len(validation),
            "delta_rho": round(delta, 4) if delta is not None else None,
            "delta_ci": ([round(ci[0], 4), round(ci[1], 4)]
                         if ci is not None else None),
            "monotonicity": mono, "passed": passed}


def gate2_candidate(name: str, fitted, train: list[HypoTrade],
                    sealed: list[HypoTrade]) -> dict:
    """Sealed window, opened once: sign-positive Delta-rho AND monotone."""
    stat = _delta_stat(name, fitted)
    delta = stat(sealed)
    edges = train_quartile_edges(
        [score_trade(name, fitted, t) for t in train])
    mono = monotone_by_edges(sealed, name, fitted, edges)
    passed = (len(sealed) >= PANEL_FLOOR and delta is not None
              and delta > 0 and mono["monotone"])
    return {"n": len(sealed),
            "delta_rho": round(delta, 4) if delta is not None else None,
            "monotonicity": mono, "passed": passed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_stats.py -q`
Expected: 7 passed. If `test_gate1_passes_repairing_candidate_and_fails_identity` fails on the CI-clean assertion (bootstrap variance), the synthetic panel is too weak — raise `n_blocks` in `_gate_panel` (e.g. to 100); do NOT loosen the gate.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/test_engine_repair_stats.py
git diff --cached --stat
git commit -m "feat(repair): candidate dispatch + family-corrected gate statistics"
```

---

### Task 6: Gate-3 replay — qualifier stream, drawdown, cost stress

**Files:**
- Modify: `src/moonface/signal/engine/repair.py` (append)
- Test: `tests/test_engine_repair_stream.py`

**Interfaces:**
- Consumes: `simulate_entry`, `scoring_pass`, `BarRow` from calibration; `atr` from `moonface.foundation.risk`; `cost_stress` from honesty; `BASE_THRESHOLD`, `BREADTH_MIN`.
- Produces: `qualify_fn_for(name: str, fitted)` → `callable(BarRow) -> bool`, `qualifier_stream(candles, cfg, rows, qualify_fn) -> list[tuple[HypoTrade, float]]` (trade, atr_frac pairs; LONG-only, ALLOW-policy, breadth-gated, non-extreme-vol, one position at a time), `replay_metrics(pairs, cfg) -> dict` (keys `n`, `net_r`, `max_dd_r`, `cost_stress`), `gate3_replay(candles, cfg, rows, name, fitted) -> dict` (keys `baseline_v22`, `candidate`, `passed`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_stream.py
"""Gate-3 replay machinery: live-shape stream under a scoring qualifier."""
import dataclasses

from moonface.signal.engine.calibration import scoring_pass
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.repair import (
    gate3_replay,
    qualifier_stream,
    qualify_fn_for,
    replay_metrics,
)

from tests.helpers_audit import _walk_series
from tests.helpers_repair import ht


def _fixture():
    candles = _walk_series(700)
    cfg = dataclasses.replace(EngineConfig(), lookback_bars=400)
    rows = scoring_pass(cfg, candles, 380)
    return candles, cfg, rows


def test_stream_is_long_only_non_overlapping_with_atr_frac():
    candles, cfg, rows = _fixture()
    pairs = qualifier_stream(candles, cfg, rows, lambda row: True)
    prev_exit = -1
    for trade, atr_frac in pairs:
        assert trade.direction == 1
        assert trade.entry_index > prev_exit
        assert atr_frac > 0.0
        prev_exit = trade.exit_index
    assert qualifier_stream(candles, cfg, rows, lambda row: False) == []


def test_replay_metrics_drawdown_and_cost_stress():
    cfg = EngineConfig()
    pairs = [(ht(0, 70, 1.0), 0.02), (ht(10, 70, -2.0), 0.02),
             (ht(20, 70, 0.5), 0.02)]
    m = replay_metrics(pairs, cfg)
    assert m["n"] == 3
    assert abs(m["net_r"] - (-0.5)) < 1e-9
    assert abs(m["max_dd_r"] - (-2.0)) < 1e-9
    assert m["cost_stress"]["net_r_3x"] < m["cost_stress"]["net_r_1x"]


def test_identity_candidate_replays_identically_to_baseline():
    candles, cfg, rows = _fixture()
    # c1 identity: entry threshold == BASE_THRESHOLD -> same stream as v2.2
    result = gate3_replay(candles, cfg, rows, "c1_tier_merge", (40, 60, 75))
    assert result["baseline_v22"] == result["candidate"]
    assert result["passed"] == (
        result["candidate"]["n"] > 0
        and result["candidate"]["cost_stress"]["net_r_3x"] > 0)


def test_qualify_fn_dispatch():
    assert callable(qualify_fn_for("c1_tier_merge", (40, 60)))
    assert callable(qualify_fn_for("c2_side_vol", {("LONG", "normal"): 5}))
    assert callable(qualify_fn_for("c3_isotonic", ((60, 0.1),)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_stream.py -q`
Expected: FAIL with `ImportError: cannot import name 'gate3_replay'`

- [ ] **Step 3: Append the implementation to repair.py**

```python
# --- Gate 3: veto-only replay confirm (spec section 4) -----------------------

def qualify_fn_for(name: str, fitted):
    """Entry qualifier per candidate, applied on top of the common v2.2-shape
    conditions in qualifier_stream. The stream is LONG-only (v2.1 long-only is
    policy, not scoring), so C2 uses its LONG-cell offsets."""
    if name == "c1_tier_merge":
        threshold = c1_entry_threshold(fitted)
        return lambda row: row.trend.score >= threshold
    if name == "c2_side_vol":
        return lambda row: row.trend.score >= (
            BASE_THRESHOLD + fitted.get(("LONG", row.vol_state), 0))
    if name == "c3_isotonic":
        return lambda row: apply_isotonic(row.trend.score, fitted) > 0.0
    raise ValueError(f"unknown candidate: {name}")


def qualifier_stream(candles: list[Candle], cfg: EngineConfig,
                     rows: list[BarRow], qualify_fn,
                     ) -> list[tuple[HypoTrade, float]]:
    """One-position-at-a-time trend stream in the live v2.2 shape: LONG only,
    ALLOW policy, breadth gate, non-extreme vol — plus the candidate's scoring
    qualifier. Returns (trade, atr_frac) for cost stress."""
    pairs: list[tuple[HypoTrade, float]] = []
    busy_until = -1
    for row in rows:
        if row.index <= busy_until:
            continue
        state = row.trend
        if state.direction != 1 or row.vol_state == "extreme":
            continue
        if state.policy != "ALLOW" or state.breadth < BREADTH_MIN:
            continue
        if not qualify_fn(row):
            continue
        trade = simulate_entry(candles, cfg, row, "trend")
        if trade is None:
            break
        tail = candles[max(0, row.index - cfg.atr_period):row.index + 1]
        close = candles[row.index].close
        atr_frac = atr(tail, cfg.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs


def replay_metrics(pairs: list[tuple[HypoTrade, float]],
                   cfg: EngineConfig) -> dict:
    ordered = sorted(pairs, key=lambda p: p[0].exit_ts_ms)
    rs = [t.net_r for t, _ in ordered]
    cum = peak = dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    stress = cost_stress([(t.exit_ts_ms, t.net_r, af, cfg.base_fraction)
                          for t, af in ordered])
    return {"n": len(rs), "net_r": round(sum(rs), 4),
            "max_dd_r": round(dd, 4), "cost_stress": stress}


def gate3_replay(candles: list[Candle], cfg: EngineConfig,
                 rows: list[BarRow], name: str, fitted) -> dict:
    """Confirm/veto only — both legs run the IDENTICAL machinery, so this is
    an apples-to-apples comparison (the registration's sanity numbers are
    context, not the baseline)."""
    base_pairs = qualifier_stream(
        candles, cfg, rows,
        lambda row: row.trend.score >= BASE_THRESHOLD)
    cand_pairs = qualifier_stream(candles, cfg, rows,
                                  qualify_fn_for(name, fitted))
    base = replay_metrics(base_pairs, cfg)
    cand = replay_metrics(cand_pairs, cfg)
    passed = (cand["n"] > 0
              and cand["net_r"] >= base["net_r"]
              and abs(cand["max_dd_r"]) <= abs(base["max_dd_r"])
              and cand["cost_stress"]["net_r_3x"] > 0)
    return {"baseline_v22": base, "candidate": cand, "passed": passed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_stream.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/test_engine_repair_stream.py
git diff --cached --stat
git commit -m "feat(repair): gate-3 qualifier stream, drawdown, cost stress"
```

---

### Task 7: Report builder — fit, gates, sealed protection, verdict

**Files:**
- Modify: `src/moonface/signal/engine/repair.py` (append)
- Test: `tests/test_engine_repair_report.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6; `overlapping_panel`, `scoring_pass`, `series_fingerprint`, `engine_hash`.
- Produces: `fitted_payload(fitted: dict) -> dict` (JSON-safe), `fitted_from_payload(payload: dict) -> dict` (inverse; used by the shadow sidecar), `build_repair_report(cfg, candles, warmup, train_end_ts_ms=..., sealed_start_ts_ms=...) -> dict` with keys `engine_hash`, `label`, `data`, `frozen_analysis_constants`, `panel_counts`, `segments`, `fitted`, `gate1`, `survivor`, `gate2`, `gate3`, `verdict`. Verdict is one of `CLOSED_NEGATIVE_GATE1`, `CLOSED_NEGATIVE_GATE2`, `CLOSED_NEGATIVE_GATE3`, `ALL_GATES_PASSED_HUMAN_DECISION_PENDING`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_report.py
"""Report assembly: sealed protection, verdict routing, JSON safety."""
import dataclasses
import json

from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.repair import (
    CANDIDATES,
    build_repair_report,
    fitted_from_payload,
    fitted_payload,
)

from tests.helpers_audit import H, _walk_series

_VERDICTS = {
    "CLOSED_NEGATIVE_GATE1", "CLOSED_NEGATIVE_GATE2",
    "CLOSED_NEGATIVE_GATE3", "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
}


def test_fitted_payload_roundtrip():
    fitted = {
        "c1_tier_merge": (40, 60),
        "c2_side_vol": {("LONG", "normal"): 5, ("SHORT", "high"): 20},
        "c3_isotonic": ((40, -0.1), (70, 0.2)),
    }
    back = fitted_from_payload(fitted_payload(fitted))
    assert back["c1_tier_merge"] == (40, 60)
    assert back["c2_side_vol"][("LONG", "normal")] == 5
    assert back["c2_side_vol"][("SHORT", "high")] == 20
    assert back["c3_isotonic"] == ((40, -0.1), (70, 0.2))


def test_report_structure_and_sealed_protection():
    candles = _walk_series(700)
    cfg = dataclasses.replace(EngineConfig(), lookback_bars=400)
    report = build_repair_report(cfg, candles, 380,
                                 train_end_ts_ms=350 * H,
                                 sealed_start_ts_ms=550 * H)
    assert set(CANDIDATES) == set(report["gate1"])
    assert report["verdict"] in _VERDICTS
    assert report["label"].startswith("trend-score repair")
    # sealed protection: no survivor -> gate2/gate3 never computed
    if report["survivor"] is None:
        assert report["verdict"] == "CLOSED_NEGATIVE_GATE1"
        assert report["gate2"] is None and report["gate3"] is None
    json.dumps(report)  # must be JSON-serializable as-is
    assert report["data"]["scored_bars"] == 700 - 380
    assert report["segments"]["train"] >= 0
    assert "dropped" in report["segments"]


def test_fitting_sees_only_train_trades(monkeypatch):
    """No-lookahead (spec section 6): every trade handed to a fitter exited
    before the train boundary."""
    import moonface.signal.engine.repair as repair

    seen = {}
    real = repair.fit_tier_merge

    def spy(train):
        seen["train"] = list(train)
        return real(train)

    monkeypatch.setattr(repair, "fit_tier_merge", spy)
    candles = _walk_series(700)
    cfg = dataclasses.replace(EngineConfig(), lookback_bars=400)
    repair.build_repair_report(cfg, candles, 380,
                               train_end_ts_ms=500 * H,
                               sealed_start_ts_ms=600 * H)
    assert "train" in seen
    assert all(t.exit_ts_ms < 500 * H for t in seen["train"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_report.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_repair_report'`

- [ ] **Step 3: Append the implementation to repair.py**

```python
# --- report assembly (spec sections 1, 4) ------------------------------------

def fitted_payload(fitted: dict) -> dict:
    """JSON-safe serialization of all fitted candidate constants. The shadow
    sidecar reloads these via fitted_from_payload."""
    return {
        "c1_tier_merge": {
            "kept_edges": list(fitted["c1_tier_merge"]),
            "entry_threshold": c1_entry_threshold(fitted["c1_tier_merge"]),
        },
        "c2_side_vol": {
            f"{side}:{vol}": off
            for (side, vol), off in sorted(fitted["c2_side_vol"].items())
        },
        "c3_isotonic": [[s, v] for s, v in fitted["c3_isotonic"]],
    }


def fitted_from_payload(payload: dict) -> dict:
    offsets = {}
    for key, off in payload["c2_side_vol"].items():
        side, vol = key.split(":")
        offsets[(side, vol)] = off
    return {
        "c1_tier_merge": tuple(payload["c1_tier_merge"]["kept_edges"]),
        "c2_side_vol": offsets,
        "c3_isotonic": tuple((int(s), float(v))
                             for s, v in payload["c3_isotonic"]),
    }


def build_repair_report(cfg: EngineConfig, candles: list[Candle],
                        warmup: int,
                        train_end_ts_ms: int = TRAIN_END_TS_MS,
                        sealed_start_ts_ms: int = SEALED_START_TS_MS) -> dict:
    """Single registered evaluation: fit on train, Gate 1 on validation for
    all three candidates, Gates 2-3 for the sole survivor only. The sealed
    segment is touched exclusively inside this gate flow."""
    rows = scoring_pass(cfg, candles, warmup)
    panel, counts = overlapping_panel(candles, cfg, rows, "trend")
    segments, dropped = segment_panel(panel, train_end_ts_ms,
                                      sealed_start_ts_ms)
    fitted = {
        "c1_tier_merge": fit_tier_merge(segments["train"]),
        "c2_side_vol": fit_side_vol_offsets(segments["train"]),
        "c3_isotonic": fit_isotonic(segments["train"]),
    }
    gate1 = {
        name: gate1_candidate(name, fitted[name], segments["train"],
                              segments["validation"])
        for name in CANDIDATES
    }
    passers = [n for n in CANDIDATES if gate1[n]["passed"]]
    survivor = (max(passers, key=lambda n: gate1[n]["delta_rho"])
                if passers else None)
    gate2 = gate3 = None
    if survivor is None:
        verdict = "CLOSED_NEGATIVE_GATE1"
    else:
        gate2 = gate2_candidate(survivor, fitted[survivor],
                                segments["train"], segments["sealed"])
        if not gate2["passed"]:
            verdict = "CLOSED_NEGATIVE_GATE2"
        else:
            gate3 = gate3_replay(candles, cfg, rows, survivor,
                                 fitted[survivor])
            verdict = ("ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
                       if gate3["passed"] else "CLOSED_NEGATIVE_GATE3")
    return {
        "engine_hash": engine_hash(cfg),
        "label": REPAIR_LABEL,
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
            "train_end_ts_ms": train_end_ts_ms,
            "sealed_start_ts_ms": sealed_start_ts_ms,
            "purge_ms": PURGE_MS,
            "family_alpha": FAMILY_ALPHA,
            "n_candidates": N_CANDIDATES,
            "ci_lo_q": CI_LO_Q,
            "ci_hi_q": CI_HI_Q,
            "offset_grid": list(OFFSET_GRID),
            "cell_floor": CELL_FLOOR,
            "mono_bucket_floor": MONO_BUCKET_FLOOR,
            "panel_floor": PANEL_FLOOR,
            "block_bars": BLOCK_BARS,
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "panel_counts": counts,
        "segments": {"train": len(segments["train"]),
                     "validation": len(segments["validation"]),
                     "sealed": len(segments["sealed"]),
                     "dropped": dropped},
        "fitted": fitted_payload(fitted),
        "gate1": gate1,
        "survivor": survivor,
        "gate2": gate2,
        "gate3": gate3,
        "verdict": verdict,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_report.py -q`
Expected: 3 passed

- [ ] **Step 5: Run the full repair suite**

Run: `.venv/bin/pytest tests/test_engine_repair_splits.py tests/test_engine_repair_c1.py tests/test_engine_repair_c2.py tests/test_engine_repair_c3.py tests/test_engine_repair_stats.py tests/test_engine_repair_stream.py tests/test_engine_repair_report.py -q`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/repair.py tests/test_engine_repair_report.py
git diff --cached --stat
git commit -m "feat(repair): report builder with sealed protection + verdict routing"
```

---

### Task 8: CLI `tools/engine_repair.py`

**Files:**
- Create: `tools/engine_repair.py`
- Test: `tests/test_engine_repair_cli.py`

**Interfaces:**
- Consumes: `build_repair_report`, `SEALED_START_TS_MS`; `load_bundle` from `moonface.foundation.bundle`; `load_engine_config`.
- Produces: `run(argv) -> int` (0 ok; 2 mechanical refusal), `main()`. Registered invocation: `.venv/bin/python -m tools.engine_repair --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 --out experiments/engine/repair_report_2026-07.json`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_cli.py
"""Repair CLI: report file, mechanical-failure exits, sealed-length guard.

Hermetic: load_bundle is monkeypatched (audit-CLI precedent).
"""
import json

from moonface.foundation.bundle import DataBundle
import tools.engine_repair as cli

from tests.helpers_audit import H, _walk_series


def _patch_bundle(monkeypatch, n=700):
    candles = _walk_series(n)
    monkeypatch.setattr(
        cli, "load_bundle", lambda *a, **kw: DataBundle(candles=candles))
    return candles


def _base_args(tmp_path):
    return [
        "--start-ms", "0",
        "--end-ms", str(700 * H),
        "--warmup", "380",
        "--engine", "promotion/engine.json",
        "--lookback-bars", "400",
        "--train-end-ms", str(350 * H),
        "--sealed-start-ms", str(550 * H),
        "--out", str(tmp_path / "report.json"),
    ]


def test_writes_report(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    assert cli.run(_base_args(tmp_path)) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert "verdict" in report and "gate1" in report and "fitted" in report


def test_truncated_data_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch, n=100)
    assert cli.run(_base_args(tmp_path)) == 2
    assert not (tmp_path / "report.json").exists()


def test_short_sealed_segment_exits_2_without_overrides(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)  # last ts 699H << frozen sealed start + 1y
    args = [
        "--start-ms", "0", "--end-ms", str(700 * H), "--warmup", "380",
        "--engine", "promotion/engine.json", "--lookback-bars", "400",
        "--out", str(tmp_path / "report.json"),
    ]
    assert cli.run(args) == 2
    assert not (tmp_path / "report.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.engine_repair'`

- [ ] **Step 3: Write the CLI**

```python
# tools/engine_repair.py
"""Pre-registered trend-score repair evaluation CLI.

Runs the single registered evaluation of the three audit-licensed trend-book
scoring repairs and emits the registered report JSON.

Spec: docs/research-log/specs/2026-07-05-trend-score-repair-design.md
Pre-reg: experiments/engine/TREND_SCORE_REPAIR_2026-07.md

DIAGNOSTIC ONLY - never gates capital, never mutates state, never changes a
frozen constant. The v2.2 forward-paper clock is unaffected; any v2.3 is a
separate human-gated registration.

Registered usage:
  .venv/bin/python -m tools.engine_repair \
      --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
      --out experiments/engine/repair_report_2026-07.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json

from moonface.foundation.bundle import load_bundle
from moonface.signal.engine.config import load_engine_config
from moonface.signal.engine.repair import (
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    build_repair_report,
)

YEAR_MS = 365 * 24 * 3_600_000


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-repair")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000,
                   help="first scored bar has a full lookback window")
    p.add_argument("--out", default=None)
    p.add_argument("--lookback-bars", type=int, default=None,
                   help="test-only window override; registered runs omit it")
    p.add_argument("--train-end-ms", type=int, default=TRAIN_END_TS_MS,
                   help="test-only boundary override; registered runs omit it")
    p.add_argument("--sealed-start-ms", type=int,
                   default=SEALED_START_TS_MS,
                   help="test-only boundary override; registered runs omit it")
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
              f"{args.warmup} - truncated data, refusing to run")
        return 2

    if (args.sealed_start_ms == SEALED_START_TS_MS
            and bundle.candles[-1].timestamp_ms
            < SEALED_START_TS_MS + YEAR_MS):
        print("ERROR: sealed segment shorter than 12 months - "
              "refusing to run (spec section 2)")
        return 2

    report = build_repair_report(cfg, bundle.candles, args.warmup,
                                 train_end_ts_ms=args.train_end_ms,
                                 sealed_start_ts_ms=args.sealed_start_ms)
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

Run: `.venv/bin/pytest tests/test_engine_repair_cli.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/engine_repair.py tests/test_engine_repair_cli.py
git diff --cached --stat
git commit -m "feat(repair): engine_repair CLI with mechanical-failure exits"
```

---

### Task 9: Freeze the pre-registration document

**Files:**
- Create: `experiments/engine/TREND_SCORE_REPAIR_2026-07.md`

No code. This document must be committed BEFORE the registered run (Task 10). Its content is frozen from the spec and the constants implemented in Tasks 1–8:

- [ ] **Step 1: Write the pre-registration document**

```markdown
# TREND SCORE REPAIR — Pre-Registration (2026-07)

**Status: FROZEN before the registered run. One registered run; re-runs only
for demonstrated mechanical failure, documented here.**

Spec: `docs/research-log/specs/2026-07-05-trend-score-repair-design.md`
Engine under test: Confluence v2.2, hash
`b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5` (LIVE,
forward clock unaffected; this lane is read-only).

## Question

Does any of exactly three audit-licensed repairs of the TREND-book scoring
order outcomes better than the frozen v2.2 scoring, out of sample, surviving
a sealed window and a veto-only replay? Promotion to v2.3 is a human decision
even on full pass.

## Registered command

    .venv/bin/python -m tools.engine_repair \
        --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
        --out experiments/engine/repair_report_2026-07.json

## Frozen constants

| constant | value |
|---|---|
| TRAIN_END_TS_MS | 1688169600000 (2023-07-01T00:00:00Z) |
| SEALED_START_TS_MS | 1748736000000 (2025-06-01T00:00:00Z) |
| PURGE_MS | 604800000 (168 one-hour bars) |
| family alpha / correction | 0.05, Bonferroni over 3 -> CI quantiles 0.008333 / 0.991667 |
| OFFSET_GRID (C2) | 0, 5, 10, 15, 20 |
| CELL_FLOOR (C2) / MONO_BUCKET_FLOOR | 30 / 30 |
| panel floor / block bars / draws / seed | 200 / 168 / 1000 / 20260704 |
| candidate menu (frozen at 3) | c1_tier_merge, c2_side_vol, c3_isotonic |

## Gates (sequential)

1. **Gate 1 (validation):** paired Delta-rho (candidate minus v2.2, identical
   panel) block-bootstrap CI clean-positive at alpha/3 AND train-quartile
   bucket means weakly increasing AND n >= 200. Survivor = largest Delta-rho
   point estimate among passers; zero passers -> CLOSED NEGATIVE.
2. **Gate 2 (sealed, opened once, survivor only):** Delta-rho point estimate
   > 0 AND monotone AND n >= 200. Fail -> CLOSED NEGATIVE; no other candidate
   may ever use the sealed window.
3. **Gate 3 (replay confirm, veto-only):** identical-machinery long-only
   trend stream, candidate vs v2.2 qualifier: net R >= baseline, |max DD| <=
   baseline, 3x-cost net R > 0, n > 0. Runs after Gate 2 (sealed already
   open; not a second opening).

## Outcome interpretation

- Any CLOSED_NEGATIVE verdict: lane closed, published here, v2.2 runs out its
  clock untouched.
- ALL_GATES_PASSED_HUMAN_DECISION_PENDING: candidate is evidence-licensed for
  a HUMAN-gated v2.3 (new ENGINE_VERSION, new hash, new registration, fresh
  clock). The shadow sidecar (spec section 5) is built only in this case.

## Results (transcribed after the registered run)

_Empty until the registered run completes._
```

- [ ] **Step 2: Verify the frozen values against the code**

Run: `grep -n "TRAIN_END_TS_MS\|SEALED_START_TS_MS\|OFFSET_GRID\|CELL_FLOOR" src/moonface/signal/engine/repair.py | head`
Expected: values identical to the table above. Also confirm the registered window values match the audit's registered run: `grep -n "start-ms" experiments/engine/SCORING_AUDIT_2026-07.md | head -3`.

- [ ] **Step 3: Commit (pre-reg must precede the run)**

```bash
git add experiments/engine/TREND_SCORE_REPAIR_2026-07.md
git diff --cached --stat
git commit -m "docs(engine): trend-score-repair pre-registration FROZEN"
```

---

### Task 10: Verification checklist, registered run, transcription

**Files:**
- Modify: `experiments/engine/TREND_SCORE_REPAIR_2026-07.md` (results section)
- Create: `experiments/engine/repair_report_2026-07.json` (run output)

- [ ] **Step 1: Full suite green (pre-run gate)**

Run: `.venv/bin/pytest -q`
Expected: everything passes (baseline before this lane: 1862 passed / 3 skipped; now higher with the repair tests). Any failure blocks the registered run.

- [ ] **Step 2: Read-only verification against the frozen engine**

Run:
```bash
git diff 1f34ee5..HEAD --stat -- \
  src/moonface/signal/engine/confluence.py \
  src/moonface/signal/engine/config.py \
  src/moonface/signal/engine/calibration.py \
  src/moonface/signal/engine/audit.py \
  src/moonface/signal/engine/modules \
  src/moonface/signal/engine/position.py \
  src/moonface/signal/journal.py \
  promotion/
```
Expected: empty output (0 lines changed — `repair.py` is a new file and is intentionally not in this list). Also `git log --format=%b -20 | grep -i "co-authored"` must be empty.

- [ ] **Step 3: Execute the registered run (ONCE)**

Run:
```bash
.venv/bin/python -m tools.engine_repair \
    --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
    --out experiments/engine/repair_report_2026-07.json
```
Expected: exit 0 and the report JSON printed. Exit 2 = mechanical refusal (fix the mechanical cause, document in the pre-reg, re-run). A completed exit-0 run is FINAL regardless of verdict.

- [ ] **Step 4: Transcribe results into the pre-reg doc**

Replace the `## Results` placeholder line with, at minimum: verdict; per-candidate Gate-1 rows (n, delta_rho, delta_ci, monotone, passed); survivor; Gate-2/Gate-3 blocks if reached; segment sizes and dropped count; data fingerprint and engine hash from the report. State plainly which stopping condition applies.

- [ ] **Step 5: Commit run artifacts**

```bash
git add experiments/engine/repair_report_2026-07.json experiments/engine/TREND_SCORE_REPAIR_2026-07.md
git diff --cached --stat
git commit -m "results(engine): trend-score-repair registered run + transcription"
```

---

### Task 11 (CONDITIONAL): Forward-shadow sidecar — build ONLY if verdict is ALL_GATES_PASSED_HUMAN_DECISION_PENDING

If the Task-10 verdict is any `CLOSED_NEGATIVE_*`, skip this task entirely (spec section 5).

**Files:**
- Create: `tools/shadow_score.py`
- Test: `tests/test_engine_repair_shadow.py`

**Interfaces:**
- Consumes: `fitted_from_payload`, `qualify_fn_for`, `candidate_value`, `scoring_pass`; the Task-10 report JSON (survivor + fitted constants).
- Produces: `run(argv) -> int`; appends JSONL rows `{"ts_ms": int, "raw_score": int, "direction": int, "vol_state": str, "candidate": str, "candidate_value": float, "qualifies": bool}` to `experiments/engine/shadow_scores_2026-07.jsonl`, deduplicating on `ts_ms`. Human-ops invocation alongside the watch daemon; NEVER evidence for any gate.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_repair_shadow.py
"""Shadow sidecar: survivor-driven, out-of-process, dedup-append JSONL."""
import json

from moonface.foundation.bundle import DataBundle
import tools.shadow_score as cli

from tests.helpers_audit import H, _walk_series


def _report(tmp_path, survivor="c1_tier_merge"):
    report = {
        "survivor": survivor,
        "fitted": {
            "c1_tier_merge": {"kept_edges": [40, 60], "entry_threshold": 60},
            "c2_side_vol": {"LONG:normal": 0},
            "c3_isotonic": [[60, 0.1]],
        },
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    return str(path)


def _patch_bundle(monkeypatch, n=700):
    candles = _walk_series(n)
    monkeypatch.setattr(
        cli, "load_bundle", lambda *a, **kw: DataBundle(candles=candles))


def _args(tmp_path, out):
    return ["--report", _report(tmp_path), "--engine",
            "promotion/engine.json", "--start-ms", "0",
            "--end-ms", str(700 * H), "--warmup", "380",
            "--lookback-bars", "400", "--tail", "5", "--out", str(out)]


def test_appends_rows_and_dedupes(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    out = tmp_path / "shadow.jsonl"
    assert cli.run(_args(tmp_path, out)) == 0
    first = out.read_text().strip().splitlines()
    assert len(first) == 5
    row = json.loads(first[-1])
    assert row["candidate"] == "c1_tier_merge"
    assert set(row) == {"ts_ms", "raw_score", "direction", "vol_state",
                        "candidate", "candidate_value", "qualifies"}
    # second run: same rows -> nothing appended
    assert cli.run(_args(tmp_path, out)) == 0
    assert out.read_text().strip().splitlines() == first


def test_no_survivor_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    out = tmp_path / "shadow.jsonl"
    args = _args(tmp_path, out)
    args[1] = _report(tmp_path, survivor=None)
    assert cli.run(args) == 2
    assert not out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_engine_repair_shadow.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.shadow_score'`

- [ ] **Step 3: Write the sidecar CLI**

```python
# tools/shadow_score.py
"""Forward shadow scorer for the trend-score-repair survivor.

Out-of-process sidecar: recomputes the surviving candidate's score from the
candle feed and appends JSONL rows. Imports engine code read-only; adds
nothing under signal/engine, so the frozen v2.2 hash is unaffected.

NEVER evidence: excluded from all gates and any promotion argument (spec
section 5). Human ops, run alongside the watch daemon.

Usage:
  .venv/bin/python -m tools.shadow_score \
      --report experiments/engine/repair_report_2026-07.json \
      --start-ms <recent> --end-ms <now> --warmup 6000 --tail 1 \
      --out experiments/engine/shadow_scores_2026-07.jsonl
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os

from moonface.foundation.bundle import load_bundle
from moonface.signal.engine.calibration import scoring_pass
from moonface.signal.engine.config import load_engine_config
from moonface.signal.engine.repair import (
    candidate_value,
    fitted_from_payload,
    qualify_fn_for,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shadow-score")
    p.add_argument("--report", required=True,
                   help="repair report JSON with survivor + fitted constants")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000)
    p.add_argument("--tail", type=int, default=1,
                   help="append at most the latest N scored bars")
    p.add_argument("--out", required=True)
    p.add_argument("--lookback-bars", type=int, default=None,
                   help="test-only window override")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with open(args.report) as f:
        report = json.load(f)
    survivor = report.get("survivor")
    if not survivor:
        print("ERROR: report has no survivor; nothing to shadow")
        return 2
    fitted = fitted_from_payload(report["fitted"])[survivor]
    qualify = qualify_fn_for(survivor, fitted)

    cfg = load_engine_config(args.engine)
    if args.lookback_bars is not None:
        cfg = dataclasses.replace(cfg, lookback_bars=args.lookback_bars)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms,
                         args.cache_dir)
    if len(bundle.candles) <= args.warmup:
        print("ERROR: truncated data, refusing to run")
        return 2
    rows = scoring_pass(cfg, bundle.candles, args.warmup)

    seen: set[int] = set()
    if os.path.exists(args.out):
        with open(args.out) as f:
            for line in f:
                if line.strip():
                    seen.add(json.loads(line)["ts_ms"])

    appended = 0
    with open(args.out, "a") as f:
        for row in rows[-args.tail:]:
            if row.ts_ms in seen:
                continue
            f.write(json.dumps({
                "ts_ms": row.ts_ms,
                "raw_score": row.trend.score,
                "direction": row.trend.direction,
                "vol_state": row.vol_state,
                "candidate": survivor,
                "candidate_value": candidate_value(
                    survivor, fitted, row.trend.score,
                    row.trend.direction, row.vol_state),
                "qualifies": bool(qualify(row)),
            }) + "\n")
            appended += 1
    print(f"appended {appended} shadow rows for {survivor}")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_engine_repair_shadow.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tools/shadow_score.py tests/test_engine_repair_shadow.py
git diff --cached --stat
git commit -m "feat(repair): forward-shadow sidecar for the surviving candidate"
```

---

## Watch-fors (from the last two lanes' post-mortems)

- Do NOT bend a plan test expectation into the implementation (the audit lane's LOO short-circuit defect began as a bad test the implementer satisfied). If a plan test looks wrong, STOP and flag it — do not make the code match it silently.
- Do NOT skip planned tests (the v2.2 lane's implementer skipped two decide()-level tests). Every test in this plan must exist verbatim or stricter.
- The sealed segment is evaluated ONLY inside `build_repair_report`'s gate flow. Never write an ad-hoc script or REPL probe against the sealed window.
- Test failure caused by bootstrap variance in synthetic gate panels → strengthen the synthetic effect, never weaken a gate.
