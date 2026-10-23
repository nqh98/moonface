# Path Signal Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the model-agnostic foundation for the BTC distributional path signal program — a point-in-time feature/label dataset, a leak-proof purged/embargoed walk-forward harness, a cost model, a LONG/SHORT/WAIT decision policy, and a dual-risk-frame evaluation gate — proven end-to-end with a trivial baseline predictor.

**Architecture:** A new isolated subpackage `src/moonface/research/pathsig/` holds the pipeline. At each 4h bar a feature row is built strictly from data at-or-before the bar's close (multi-timeframe alignment is index-based and close-time-gated to prevent lookahead). The label is the forward path `(ret_r, mae_r, mfe_r)` over horizon `h`, reusing the already-tested `event_outcome()` from `drift_screen.py`. A predictor is just a `Callable` mapping a feature vector to a `Distribution`; the policy turns a `Distribution` into a sized LONG/SHORT/WAIT `Decision`; the evaluator scores a decision stream under both the risk-adjusted (sized, MAR/Sharpe/DSR) and fixed −15R-cap frames. No model library is introduced in this plan — rungs 1–3 are separate plans.

**Tech Stack:** Python 3.11, standard library only (`dataclasses`, `statistics`, `math`, `bisect`), `pytest`, `ruff`. Reuses existing modules: `moonface.research.drift_screen.event_outcome`, `moonface.research.metrics` (DSR + equity), `moonface.research.bundle.DataBundle`, `moonface.research.multifamily_loader`.

**Scope note:** This plan delivers rung-0 plumbing only (dataset + harness + policy + gate + a constant baseline predictor). Rung 1 (regime-weighted ensemble of existing signals), rung 2 (gradient-boosted path model), and rung 3 (sequence model) are follow-on plans that consume these interfaces. The frozen feature/label/split definitions in Task 1 are the pre-registration that those plans must not silently change.

---

## File Structure

- Create: `src/moonface/research/pathsig/__init__.py` — subpackage marker + public re-exports.
- Create: `src/moonface/research/pathsig/labels.py` — `PathLabel`, `build_labels`.
- Create: `src/moonface/research/pathsig/htf.py` — `align_htf_index` (multi-timeframe, leak-proof).
- Create: `src/moonface/research/pathsig/features.py` — `FEATURE_NAMES`, feature-group builders, `build_feature_rows`, `to_vector`.
- Create: `src/moonface/research/pathsig/dataset.py` — `Sample`, `build_dataset` (feature+label join, drops incomplete rows).
- Create: `src/moonface/research/pathsig/walkforward.py` — `Fold`, `walk_forward_folds` (anchored, purged, embargoed).
- Create: `src/moonface/research/pathsig/costs.py` — `apply_costs`.
- Create: `src/moonface/research/pathsig/policy.py` — `Distribution`, `Decision`, `decide`.
- Create: `src/moonface/research/pathsig/evaluate.py` — `realized_r`, `evaluate_strategy` (dual frame).
- Modify: `src/moonface/research/metrics.py` — extract `_equity_walk`, add `equity_summary_from_returns`.
- Create: `tools/path_signal.py` — CLI skeleton with a `register` subcommand.
- Create: `experiments/path_signal/PREREGISTRATION.md` — frozen design (mirrors prior programs).
- Tests (flat, per repo convention): `tests/test_pathsig_labels.py`, `tests/test_pathsig_htf.py`, `tests/test_pathsig_features.py`, `tests/test_pathsig_dataset.py`, `tests/test_pathsig_walkforward.py`, `tests/test_pathsig_costs.py`, `tests/test_pathsig_policy.py`, `tests/test_pathsig_evaluate.py`, `tests/test_pathsig_smoke.py`.

A shared test helper builds synthetic `Candle` lists; defined inline in the first test that needs it and copied where used (tests are read in isolation).

---

## Task 1: Pre-registration freeze + CLI skeleton

**Files:**
- Create: `experiments/path_signal/PREREGISTRATION.md`
- Create: `tools/path_signal.py`
- Test: `tests/test_pathsig_register.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_register.py
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_register_writes_frozen_registration(tmp_path):
    out = tmp_path / "registration.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "path_signal.py"),
         "register", "--out", str(out)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reg = json.loads(out.read_text())
    assert reg["timeframe"] == "4h"
    assert reg["horizons"] == [6, 12]
    assert reg["atr_period"] == 14
    assert reg["deploy_asset"] == "BTCUSDT"
    assert reg["dsr_threshold"] == 0.95
    assert reg["lockbox_fraction"] == 0.2
    # the frozen feature list must be non-empty and stable-ordered
    assert isinstance(reg["features"], list) and len(reg["features"]) >= 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_register.py -v`
Expected: FAIL (`tools/path_signal.py` does not exist → non-zero return code).

- [ ] **Step 3: Write the PREREGISTRATION doc**

Create `experiments/path_signal/PREREGISTRATION.md`:

```markdown
# Path Signal — Pre-Registration (frozen 2026-06-16)

Design spec: docs/research-log/specs/2026-06-16-btc-distributional-path-signal-design.md

## Frozen before any model fit
- Timeframe: 4h decisions. Horizons predicted: h ∈ {6, 12} bars.
- ATR period for the R unit: 14 (matches the prior program).
- Deployment asset: BTCUSDT. Training/feature pool: the 16-asset 4h universe
  + BTC/ETH/SOL (cross-sectional inputs only).
- Label (per 4h bar, LONG frame): (ret_r, mae_r, mfe_r) from event_outcome().
- Feature list (frozen, order-stable) — see FEATURE_NAMES in
  src/moonface/research/pathsig/features.py. No feature may be added without a
  version bump and a fresh lockbox.
- Split: anchored walk-forward, purged + embargoed by the label horizon.
  Final 20% of the series is the one-touch lockbox tail.
- Gate: deflated Sharpe ≥ 0.95, n_trials = every hyperparameter combination ×
  every rung evaluated (set by the model plans). Reported under both the
  risk-adjusted (sized MAR/Sharpe) and fixed −15R-cap frames.

## Rungs (each must beat the rung below AND clear the gate)
0. raw existing signals (baseline replay)
1. regime-weighted ensemble of existing signals
2. distributional path model (the hypothesis)
3. sequence model (optional, gated)

Kill rule: rung 2 fails to beat rung 1 OR fails the gate ⇒ the "framework was
the limiting factor" thesis is falsified on existing data; escalate to a
separate new-data program. No parameter rescue.
```

- [ ] **Step 4: Write the CLI skeleton**

Create `tools/path_signal.py`:

```python
#!/usr/bin/env python
# tools/path_signal.py
"""BTC distributional path signal CLI.

register : freeze the design (timeframe, horizons, feature list, split,
           gate) into registration.json. Run once; the file is the frozen
           pre-registration the model plans must not silently change.

Design frozen in experiments/path_signal/PREREGISTRATION.md."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.pathsig.features import FEATURE_NAMES

TIMEFRAME = "4h"
HORIZONS = [6, 12]
ATR_PERIOD = 14
DEPLOY_ASSET = "BTCUSDT"
DSR_THRESHOLD = 0.95
LOCKBOX_FRACTION = 0.2


def register(out_path: str) -> None:
    reg = {
        "timeframe": TIMEFRAME,
        "horizons": HORIZONS,
        "atr_period": ATR_PERIOD,
        "deploy_asset": DEPLOY_ASSET,
        "dsr_threshold": DSR_THRESHOLD,
        "lockbox_fraction": LOCKBOX_FRACTION,
        "features": list(FEATURE_NAMES),
    }
    Path(out_path).write_text(json.dumps(reg, indent=2))
    print(f"wrote {out_path} ({len(FEATURE_NAMES)} features frozen)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register", help="freeze the design")
    reg.add_argument("--out", default="experiments/path_signal/registration.json")
    args = parser.parse_args(argv)
    if args.cmd == "register":
        register(args.out)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: this imports `FEATURE_NAMES`, created in Task 4. Until Task 4 lands, run the test after Task 4. Implement Task 1's doc + CLI now; the register test is verified green at the end of Task 4.

- [ ] **Step 5: Commit**

```bash
git add experiments/path_signal/PREREGISTRATION.md tools/path_signal.py tests/test_pathsig_register.py
git commit -m "feat(pathsig): pre-registration doc + register CLI skeleton"
```

---

## Task 2: Path label builder

**Files:**
- Create: `src/moonface/research/pathsig/__init__.py`
- Create: `src/moonface/research/pathsig/labels.py`
- Test: `tests/test_pathsig_labels.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_labels.py
from moonface.models import Candle
from moonface.research.pathsig.labels import PathLabel, build_labels


def _candles(closes):
    # flat-range bars: high=low=close so excursions equal terminal moves
    return [Candle(timestamp_ms=i * 14_400_000, open=c, high=c, low=c,
                   close=c, volume=1.0) for i, c in enumerate(closes)]


def test_build_labels_returns_none_when_no_future_horizon():
    candles = _candles([100.0] * 20)
    labels = build_labels(candles, h=6, atr_period=14)
    assert len(labels) == len(candles)
    # last h bars cannot have a forward label
    assert all(x is None for x in labels[-6:])


def test_label_matches_event_outcome_long_frame():
    closes = [100.0 + i for i in range(40)]  # steady uptrend
    candles = _candles(closes)
    labels = build_labels(candles, h=6, atr_period=14)
    # pick a middle bar with a valid label
    lbl = labels[20]
    assert isinstance(lbl, PathLabel)
    # uptrend held LONG: terminal forward move positive, no adverse excursion
    assert lbl.ret_r > 0
    assert lbl.mae_r <= 0.0
    assert lbl.mfe_r >= lbl.ret_r
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_labels.py -v`
Expected: FAIL (module `moonface.research.pathsig` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/__init__.py`:

```python
"""BTC distributional path signal — model-agnostic foundation.

Pipeline: features (point-in-time) + labels (forward path) -> dataset ->
purged walk-forward folds -> predictor -> policy (LONG/SHORT/WAIT + size) ->
dual-frame evaluation gate. Design frozen in
experiments/path_signal/PREREGISTRATION.md."""
```

Create `src/moonface/research/pathsig/labels.py`:

```python
"""Per-bar forward path labels, reusing the already-tested event_outcome().

The label is taken in the LONG frame: ret_r is the signed forward return in R,
mae_r (<=0) the worst adverse excursion, mfe_r (>=0) the best favourable
excursion, all over a fixed horizon h. SHORT outcomes are the mirror image and
are derived at evaluation time, not stored."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.models import Candle
from moonface.research.drift_screen import event_outcome


@dataclass(frozen=True)
class PathLabel:
    ret_r: float
    mae_r: float   # <= 0
    mfe_r: float   # >= 0


def build_labels(candles: list[Candle], h: int,
                 atr_period: int) -> list[PathLabel | None]:
    """One label per candle index. None where the entry is untradeable (no ATR
    unit) or fewer than h future bars exist."""
    labels: list[PathLabel | None] = []
    for i in range(len(candles)):
        out = event_outcome(candles, i, "LONG", h, atr_period)
        labels.append(None if out is None
                      else PathLabel(ret_r=out[0], mae_r=out[1], mfe_r=out[2]))
    return labels
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_labels.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/__init__.py src/moonface/research/pathsig/labels.py tests/test_pathsig_labels.py
git commit -m "feat(pathsig): forward path label builder"
```

---

## Task 3: Multi-timeframe alignment (leak-proof)

**Files:**
- Create: `src/moonface/research/pathsig/htf.py`
- Test: `tests/test_pathsig_htf.py`

`align_htf_index` maps each base bar to the index of the latest other-timeframe
bar that is fully closed by the time the base bar closes. Works for both coarser
(1d, 1w) and finer (1h) series. Convention: a candle with open `timestamp_ms`
and duration `dur_ms` closes at `timestamp_ms + dur_ms`; it is usable at a base
bar that closes at `base.timestamp_ms + base_dur_ms` iff its close time is
≤ that. This is what prevents lookahead.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_htf.py
from moonface.models import Candle
from moonface.research.pathsig.htf import align_htf_index

H4 = 14_400_000
D1 = 86_400_000


def _bars(n, dur, start=0):
    return [Candle(timestamp_ms=start + i * dur, open=1.0, high=1.0, low=1.0,
                   close=1.0, volume=1.0) for i in range(n)]


def test_daily_bar_not_used_until_fully_closed():
    base = _bars(12, H4)          # 12 4h bars = 2 days
    daily = _bars(2, D1)          # day0 opens at t=0, closes at t=D1
    idx = align_htf_index(base, daily, base_dur_ms=H4, htf_dur_ms=D1)
    # base bar 0 closes at H4 — no daily bar has closed yet
    assert idx[0] is None
    # the 6th 4h bar (index 5) closes at 6*H4 = D1 -> day0 just closed
    assert idx[5] == 0
    # nothing should ever point at day1 (it closes at 2*D1, beyond the window)
    assert all(j is None or j == 0 for j in idx)


def test_finer_timeframe_picks_latest_closed():
    base = _bars(3, H4)                 # closes at H4, 2H4, 3H4
    hourly = _bars(12, H4 // 4)         # 1h bars
    idx = align_htf_index(base, hourly, base_dur_ms=H4, htf_dur_ms=H4 // 4)
    # base bar 0 closes at H4: latest 1h bar closing <= H4 is the one opening at
    # 3*(H4/4), index 3
    assert idx[0] == 3
    assert idx[1] == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_htf.py -v`
Expected: FAIL (module `htf` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/htf.py`:

```python
"""Leak-proof multi-timeframe alignment.

For each base bar, find the index of the latest other-timeframe bar that is
fully closed by the time the base bar closes. Returns None where no such bar
exists. Used for 1h/1d/1w state aligned onto the 4h decision grid."""
from __future__ import annotations

from bisect import bisect_right

from moonface.models import Candle


def align_htf_index(base: list[Candle], htf: list[Candle], base_dur_ms: int,
                    htf_dur_ms: int) -> list[int | None]:
    """latest htf index j with htf[j].timestamp_ms + htf_dur_ms <=
    base[i].timestamp_ms + base_dur_ms, else None."""
    close_times = [c.timestamp_ms + htf_dur_ms for c in htf]
    out: list[int | None] = []
    for c in base:
        deadline = c.timestamp_ms + base_dur_ms
        j = bisect_right(close_times, deadline) - 1
        out.append(j if j >= 0 else None)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_htf.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/htf.py tests/test_pathsig_htf.py
git commit -m "feat(pathsig): leak-proof multi-timeframe alignment"
```

---

## Task 4: Feature builder

**Files:**
- Create: `src/moonface/research/pathsig/features.py`
- Test: `tests/test_pathsig_features.py`

The frozen feature set (order-stable). All computed strictly from data at or
before the base bar's close. HTF/funding/positioning/cross-sectional inputs are
optional; a missing input yields `None` for that row (dropped in Task 5).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_features.py
from moonface.models import Candle
from moonface.research.pathsig.features import (FEATURE_NAMES,
                                                build_feature_rows, to_vector)

H4 = 14_400_000


def _candles(closes):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(timestamp_ms=i * H4, open=c, high=c * 1.01,
                          low=c * 0.99, close=c, volume=1.0))
    return out


def test_feature_names_are_frozen_and_unique():
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))
    assert "ret_1" in FEATURE_NAMES
    assert "rvol_24" in FEATURE_NAMES


def test_rows_are_none_until_warmup_satisfied():
    candles = _candles([100.0 + i for i in range(200)])
    rows = build_feature_rows(candles, atr_period=14)
    assert len(rows) == len(candles)
    # earliest bars cannot have the longest-lookback feature
    assert rows[0] is None
    # a late bar has a full row
    assert rows[150] is not None
    assert set(rows[150].keys()) == set(FEATURE_NAMES)


def test_to_vector_is_order_stable():
    candles = _candles([100.0 + i for i in range(200)])
    rows = build_feature_rows(candles, atr_period=14)
    vec = to_vector(rows[150])
    assert len(vec) == len(FEATURE_NAMES)
    # to_vector follows FEATURE_NAMES order exactly
    assert vec[FEATURE_NAMES.index("ret_1")] == rows[150]["ret_1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_features.py -v`
Expected: FAIL (module `features` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/features.py`:

```python
"""Frozen, order-stable point-in-time feature set for the 4h path model.

Every feature at base bar i uses only candles[: i+1] (closed by bar i). HTF,
funding, positioning, and cross-sectional inputs are optional kwargs; when not
supplied those features are omitted from FEATURE_NAMES coverage by yielding None
for the whole row only if a *required* base feature is missing. Optional inputs
that are None for a given bar make that row None (dropped downstream)."""
from __future__ import annotations

import math
from statistics import fmean, pstdev

from moonface.backtest.edge.evaluate import _risk
from moonface.models import Candle

# Order-stable frozen list. Base (price/vol) features are always present; the
# remaining features require their optional series and are still part of the
# frozen vector (a row missing any is dropped in build_dataset).
FEATURE_NAMES: tuple[str, ...] = (
    "ret_1", "ret_6", "ret_24",
    "rvol_24", "atr_frac",
    "ma100_dist", "donchian_pos_55",
    "htf_d1_ret_1", "htf_d1_rvol_14", "htf_w1_ret_1",
    "funding_level", "funding_slope_8",
    "oi_z", "taker_z",
    "xs_ret_rank", "xs_funding_rank",
)

_WARMUP = 100  # longest base lookback (ma100 / donchian via 55, rvol 24)


def _ret(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n < 0:
        return None
    prev = candles[i - n].close
    if prev <= 0:
        return None
    return candles[i].close / prev - 1.0


def _rvol(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n < 0:
        return None
    rets = []
    for k in range(i - n + 1, i + 1):
        p = candles[k - 1].close
        if p > 0:
            rets.append(candles[k].close / p - 1.0)
    if len(rets) < 2:
        return None
    return pstdev(rets)


def _ma_dist(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n + 1 < 0:
        return None
    ma = fmean(c.close for c in candles[i - n + 1: i + 1])
    if ma <= 0:
        return None
    return candles[i].close / ma - 1.0


def _donchian_pos(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n + 1 < 0:
        return None
    window = candles[i - n + 1: i + 1]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    if hi <= lo:
        return 0.5
    return (candles[i].close - lo) / (hi - lo)


def base_features(candles: list[Candle], i: int,
                  atr_period: int) -> dict[str, float] | None:
    """The always-present price/vol block. None until warmup satisfied."""
    if i < _WARMUP:
        return None
    unit = _risk(candles, i, 1.0, atr_period)
    close = candles[i].close
    parts = {
        "ret_1": _ret(candles, i, 1),
        "ret_6": _ret(candles, i, 6),
        "ret_24": _ret(candles, i, 24),
        "rvol_24": _rvol(candles, i, 24),
        "atr_frac": (unit / close) if (unit is not None and close > 0) else None,
        "ma100_dist": _ma_dist(candles, i, 100),
        "donchian_pos_55": _donchian_pos(candles, i, 55),
    }
    if any(v is None for v in parts.values()):
        return None
    return parts


def build_feature_rows(candles: list[Candle], atr_period: int
                       ) -> list[dict[str, float] | None]:
    """Base feature rows only (HTF/funding/positioning/cross-sectional are
    merged by build_dataset which has access to the aligned series). A row is
    None until warmup is satisfied. The keys of a non-None row are exactly the
    base block; build_dataset fills the remaining FEATURE_NAMES."""
    return [base_features(candles, i, atr_period) for i in range(len(candles))]


def to_vector(row: dict[str, float]) -> list[float]:
    """Project a complete feature dict onto FEATURE_NAMES order."""
    return [row[name] for name in FEATURE_NAMES]


def zscore(values: list[float], i: int, n: int) -> float | None:
    """Trailing z-score of values[i] over the n bars ending at i, inclusive."""
    if i - n + 1 < 0:
        return None
    window = [v for v in values[i - n + 1: i + 1] if v is not None]
    if len(window) < 2:
        return None
    mu = fmean(window)
    sd = pstdev(window)
    if sd <= 0:
        return None
    return (values[i] - mu) / sd
```

Note: `build_feature_rows` emits only the base block; Task 5 (`build_dataset`)
merges the HTF/funding/positioning/cross-sectional features so the optional
series are joined in one place. `zscore` is provided here for Task 5's use.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pathsig_features.py tests/test_pathsig_register.py -v`
Expected: PASS (the Task 1 register test now imports `FEATURE_NAMES` successfully).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/features.py tests/test_pathsig_features.py
git commit -m "feat(pathsig): frozen point-in-time feature set + register green"
```

---

## Task 5: Dataset assembler (feature+label join)

**Files:**
- Create: `src/moonface/research/pathsig/dataset.py`
- Test: `tests/test_pathsig_dataset.py`

Joins the base feature rows, the optional HTF/funding/positioning/cross-sectional
features, and the label into `Sample`s, keeping only bars where every frozen
feature and the label are present.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_dataset.py
from moonface.models import Candle
from moonface.research.bundle import DataBundle
from moonface.research.pathsig.dataset import Sample, build_dataset
from moonface.research.pathsig.features import FEATURE_NAMES

H4 = 14_400_000


def _bundle(n):
    candles, funding, feat = [], [], []
    for i in range(n):
        price = 100.0 + i * 0.5
        candles.append(Candle(timestamp_ms=i * H4, open=price, high=price * 1.01,
                              low=price * 0.99, close=price, volume=1.0))
        funding.append(0.0001)
        feat.append(1000.0 + i)   # stand-in OI/metrics series
    return DataBundle(candles=candles, funding=funding, feature=feat)


def test_samples_have_complete_vectors_and_labels():
    bundle = _bundle(300)
    samples = build_dataset(bundle, h=6, atr_period=14,
                            xs_ret_rank=[0.5] * 300, xs_funding_rank=[0.5] * 300)
    assert samples, "expected non-empty dataset"
    s = samples[0]
    assert isinstance(s, Sample)
    assert len(s.x) == len(FEATURE_NAMES)
    assert all(v is not None for v in s.x)
    assert s.label is not None
    # indices are strictly increasing and within range
    idxs = [s.index for s in samples]
    assert idxs == sorted(idxs)


def test_last_horizon_bars_excluded_for_missing_label():
    bundle = _bundle(300)
    samples = build_dataset(bundle, h=6, atr_period=14,
                            xs_ret_rank=[0.5] * 300, xs_funding_rank=[0.5] * 300)
    assert max(s.index for s in samples) < 300 - 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_dataset.py -v`
Expected: FAIL (module `dataset` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/dataset.py`:

```python
"""Join features + label into Sample rows, keeping only fully-populated bars.

The optional HTF/funding/positioning/cross-sectional features are computed here
because this is where the aligned series live. A bar is kept only when every
frozen feature in FEATURE_NAMES and the label are present."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.research.bundle import DataBundle
from moonface.research.pathsig.features import (FEATURE_NAMES,
                                                build_feature_rows, to_vector,
                                                zscore)
from moonface.research.pathsig.htf import align_htf_index
from moonface.research.pathsig.labels import PathLabel, build_labels

H4_MS = 14_400_000
D1_MS = 86_400_000
W1_MS = 604_800_000


def _slope(values: list[float | None], i: int, n: int) -> float | None:
    if i - n < 0 or values[i] is None or values[i - n] is None:
        return None
    return values[i] - values[i - n]


def build_dataset(bundle: DataBundle, h: int, atr_period: int,
                  xs_ret_rank: list[float | None],
                  xs_funding_rank: list[float | None],
                  d1_candles=None, w1_candles=None) -> list["Sample"]:
    """One asset -> list of complete Samples. d1_candles/w1_candles are the same
    asset's daily/weekly series for the HTF block; when None those features are
    treated as missing and every row is dropped (so HTF series are required for
    a usable dataset, by design)."""
    candles = bundle.candles
    n = len(candles)
    base = build_feature_rows(candles, atr_period)
    labels = build_labels(candles, h, atr_period)
    funding = bundle.funding or [None] * n
    oi = bundle.feature or [None] * n

    d1_idx = (align_htf_index(candles, d1_candles, H4_MS, D1_MS)
              if d1_candles else [None] * n)
    w1_idx = (align_htf_index(candles, w1_candles, H4_MS, W1_MS)
              if w1_candles else [None] * n)

    samples: list[Sample] = []
    for i in range(n):
        if base[i] is None or labels[i] is None:
            continue
        row = dict(base[i])
        row["htf_d1_ret_1"] = _d1_ret(d1_candles, d1_idx, i, 1)
        row["htf_d1_rvol_14"] = _d1_rvol(d1_candles, d1_idx, i, 14)
        row["htf_w1_ret_1"] = _d1_ret(w1_candles, w1_idx, i, 1)
        row["funding_level"] = funding[i]
        row["funding_slope_8"] = _slope(funding, i, 8)
        row["oi_z"] = zscore(oi, i, 180) if oi[i] is not None else None
        row["taker_z"] = zscore(oi, i, 180) if oi[i] is not None else None
        row["xs_ret_rank"] = xs_ret_rank[i]
        row["xs_funding_rank"] = xs_funding_rank[i]
        if any(row.get(name) is None for name in FEATURE_NAMES):
            continue
        samples.append(Sample(index=i, timestamp_ms=candles[i].timestamp_ms,
                              x=to_vector(row), label=labels[i]))
    return samples


def _d1_ret(d1, d1_idx, i, n):
    if not d1 or d1_idx[i] is None or d1_idx[i] - n < 0:
        return None
    j = d1_idx[i]
    prev = d1[j - n].close
    return d1[j].close / prev - 1.0 if prev > 0 else None


def _d1_rvol(d1, d1_idx, i, n):
    from statistics import pstdev
    if not d1 or d1_idx[i] is None or d1_idx[i] - n < 0:
        return None
    j = d1_idx[i]
    rets = []
    for k in range(j - n + 1, j + 1):
        p = d1[k - 1].close
        if p > 0:
            rets.append(d1[k].close / p - 1.0)
    return pstdev(rets) if len(rets) >= 2 else None


@dataclass(frozen=True)
class Sample:
    index: int
    timestamp_ms: int
    x: list[float]
    label: PathLabel
```

Note: the test passes `d1_candles`/`w1_candles` via a constructed daily series.
Update the test helper to supply them — amend `_bundle` is unnecessary; instead
pass daily/weekly built from the same closes. Add to the test file:

```python
def _daily(n):
    return [Candle(timestamp_ms=i * 86_400_000, open=100.0 + i, high=101.0 + i,
                  low=99.0 + i, close=100.0 + i, volume=1.0) for i in range(n)]
```

and call `build_dataset(..., d1_candles=_daily(60), w1_candles=_daily(20))` so
the HTF block is populated. Without HTF series the dataset is intentionally
empty (HTF features are required). Adjust both test calls accordingly before
running Step 4.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_dataset.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/dataset.py tests/test_pathsig_dataset.py
git commit -m "feat(pathsig): dataset assembler joining features, HTF, and labels"
```

---

## Task 6: Purged + embargoed walk-forward folds

**Files:**
- Create: `src/moonface/research/pathsig/walkforward.py`
- Test: `tests/test_pathsig_walkforward.py`

Anchored expanding train window; each test block is separated from its training
data by an embargo of `h` samples on each side so the overlapping-horizon labels
cannot leak. The final `lockbox_fraction` of samples is never returned as a
normal fold — it is the sealed tail.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_walkforward.py
from moonface.research.pathsig.walkforward import Fold, walk_forward_folds


def test_train_and_test_are_purged_by_embargo():
    n = 1000
    folds = walk_forward_folds(n_samples=n, n_folds=4, embargo=6,
                               lockbox_fraction=0.2)
    assert folds
    for f in folds:
        assert isinstance(f, Fold)
        # no train index within `embargo` of any test index
        lo, hi = min(f.test_idx), max(f.test_idx)
        assert all(ti < lo - 6 or ti > hi + 6 for ti in f.train_idx)
        # anchored: training starts at 0
        assert min(f.train_idx) == 0


def test_lockbox_tail_is_excluded_from_all_folds():
    n = 1000
    folds = walk_forward_folds(n_samples=n, n_folds=4, embargo=6,
                               lockbox_fraction=0.2)
    lockbox_start = int(n * 0.8)
    for f in folds:
        assert max(f.test_idx) < lockbox_start
        assert max(f.train_idx) < lockbox_start
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_walkforward.py -v`
Expected: FAIL (module `walkforward` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/walkforward.py`:

```python
"""Anchored, purged, embargoed walk-forward folds over sample positions.

Sample positions are 0..n_samples-1 (positions into the dataset, not candle
indices). The final lockbox_fraction is the sealed tail and is never part of a
fold. Each test block is separated from training by `embargo` positions on each
side so labels that span future bars cannot leak across the boundary."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fold:
    train_idx: list[int]
    test_idx: list[int]


def walk_forward_folds(n_samples: int, n_folds: int, embargo: int,
                       lockbox_fraction: float) -> list[Fold]:
    usable = int(n_samples * (1.0 - lockbox_fraction))
    if n_folds < 1 or usable < n_folds * (embargo + 2):
        return []
    block = usable // (n_folds + 1)          # first block is the seed train set
    folds: list[Fold] = []
    for k in range(1, n_folds + 1):
        test_lo = block * k
        test_hi = block * (k + 1) if k < n_folds else usable
        test_idx = list(range(test_lo, test_hi))
        train_idx = [i for i in range(0, test_lo - embargo) if i >= 0]
        if not train_idx or not test_idx:
            continue
        folds.append(Fold(train_idx=train_idx, test_idx=test_idx))
    return folds
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_walkforward.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/walkforward.py tests/test_pathsig_walkforward.py
git commit -m "feat(pathsig): purged embargoed walk-forward folds with sealed tail"
```

---

## Task 7: Cost model

**Files:**
- Create: `src/moonface/research/pathsig/costs.py`
- Test: `tests/test_pathsig_costs.py`

Converts gross R to net R after round-trip taker fees, slippage, and funding.
Fees/slippage are fractions of notional; 1 R of price move = `atr_frac` of
notional, so a fee of `c` fraction of notional costs `c / atr_frac` R.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_costs.py
from moonface.research.pathsig.costs import apply_costs


def test_costs_reduce_gross_r():
    net = apply_costs(gross_r=2.0, atr_frac=0.02, taker_bps=5.0,
                      slippage_bps=2.0, funding_r=0.1)
    # round-trip taker = 2*5bps = 0.001 of notional -> 0.001/0.02 = 0.05 R
    # slippage round-trip = 2*2bps = 0.0004 -> 0.02 R; funding 0.1 R
    assert net == round(2.0 - 0.05 - 0.02 - 0.1, 6)


def test_tighter_stop_costs_more_r():
    # smaller atr_frac (tighter ATR relative to price) => fees cost more in R
    wide = apply_costs(2.0, atr_frac=0.05, taker_bps=5.0, slippage_bps=0.0,
                       funding_r=0.0)
    tight = apply_costs(2.0, atr_frac=0.01, taker_bps=5.0, slippage_bps=0.0,
                        funding_r=0.0)
    assert tight < wide
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_costs.py -v`
Expected: FAIL (module `costs` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/costs.py`:

```python
"""Gross-R -> net-R cost model: round-trip taker fee + slippage + funding.

Fees and slippage are fractions of notional; since 1 R of price move equals
atr_frac of notional, a notional cost c becomes c / atr_frac in R. funding_r is
supplied already in R (signed accrual over the hold)."""
from __future__ import annotations


def apply_costs(gross_r: float, atr_frac: float, taker_bps: float,
                slippage_bps: float, funding_r: float) -> float:
    if atr_frac <= 0:
        return gross_r - funding_r
    taker_frac = 2.0 * taker_bps / 1e4        # entry + exit
    slip_frac = 2.0 * slippage_bps / 1e4
    cost_r = (taker_frac + slip_frac) / atr_frac
    return round(gross_r - cost_r - funding_r, 6)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_costs.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/costs.py tests/test_pathsig_costs.py
git commit -m "feat(pathsig): gross-to-net R cost model"
```

---

## Task 8: Decision policy (LONG/SHORT/WAIT + sizing)

**Files:**
- Create: `src/moonface/research/pathsig/policy.py`
- Test: `tests/test_pathsig_policy.py`

WAIT is the default. Direction comes from the sign of expected return; the
risk-adjusted edge `exp_ret_r / |exp_mae_r|` must clear a calibrated threshold to
trade. Size is conviction-scaled and hard-capped.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_policy.py
from moonface.research.pathsig.policy import Decision, Distribution, decide


def test_low_edge_waits():
    dist = Distribution(p_up=0.52, exp_ret_r=0.05, exp_mae_r=-1.0, exp_mfe_r=1.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=1.0, max_fraction=0.02)
    assert d.action == "WAIT"
    assert d.size == 0.0


def test_strong_positive_edge_goes_long_and_sizes():
    dist = Distribution(p_up=0.7, exp_ret_r=0.8, exp_mae_r=-1.0, exp_mfe_r=2.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=0.02, max_fraction=0.02)
    assert d.action == "LONG"
    assert 0.0 < d.size <= 0.02


def test_negative_edge_goes_short():
    dist = Distribution(p_up=0.3, exp_ret_r=-0.8, exp_mae_r=-1.0, exp_mfe_r=2.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=0.02, max_fraction=0.02)
    assert d.action == "SHORT"


def test_size_is_capped():
    dist = Distribution(p_up=0.99, exp_ret_r=50.0, exp_mae_r=-0.1, exp_mfe_r=99.0)
    d = decide(dist, edge_threshold=0.2, kelly_scale=10.0, max_fraction=0.02)
    assert d.size == 0.02
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_policy.py -v`
Expected: FAIL (module `policy` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/policy.py`:

```python
"""Distribution -> LONG/SHORT/WAIT decision with conviction sizing.

The edge is exp_ret_r / |exp_mae_r| (drift per unit of predicted adverse
excursion) — the quantity the prior program could never harvest. WAIT is the
default; |edge| must clear edge_threshold (calibrated on training folds) to
trade. Size scales with the excess edge, hard-capped at max_fraction."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Distribution:
    p_up: float
    exp_ret_r: float
    exp_mae_r: float   # <= 0
    exp_mfe_r: float   # >= 0


@dataclass(frozen=True)
class Decision:
    action: str        # "LONG" | "SHORT" | "WAIT"
    size: float        # fraction of equity, >= 0


def decide(dist: Distribution, edge_threshold: float, kelly_scale: float,
           max_fraction: float) -> Decision:
    denom = abs(dist.exp_mae_r)
    if denom <= 0.0:
        return Decision("WAIT", 0.0)
    edge = dist.exp_ret_r / denom
    if abs(edge) < edge_threshold:
        return Decision("WAIT", 0.0)
    size = min(max_fraction, (abs(edge) - edge_threshold) * kelly_scale)
    if size <= 0.0:
        return Decision("WAIT", 0.0)
    return Decision("LONG" if edge > 0 else "SHORT", round(size, 6))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_policy.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/policy.py tests/test_pathsig_policy.py
git commit -m "feat(pathsig): WAIT-default decision policy with conviction sizing"
```

---

## Task 9: Dual-frame strategy evaluation + metrics refactor

**Files:**
- Modify: `src/moonface/research/metrics.py` (extract `_equity_walk`, add `equity_summary_from_returns`)
- Create: `src/moonface/research/pathsig/evaluate.py`
- Test: `tests/test_pathsig_evaluate.py`

`realized_r` maps a decision + label to terminal net R in the chosen direction
(holding to horizon h). `evaluate_strategy` reports both frames: risk-adjusted
(sized equity → Sharpe/MAR/DSR) and fixed-cap (unsized R sum, max R drawdown,
−15R pass/fail).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_evaluate.py
from moonface.research.metrics import equity_summary_from_returns
from moonface.research.pathsig.evaluate import evaluate_strategy, realized_r
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Decision


def test_equity_summary_from_returns_matches_manual_walk():
    s = equity_summary_from_returns([0.1, -0.05, 0.2])
    # 1.1 * 0.95 * 1.2 = 1.254 -> net 0.254
    assert s.net_return == round(1.1 * 0.95 * 1.2 - 1.0, 6)
    assert s.trade_count == 3


def test_realized_r_directions():
    lbl = PathLabel(ret_r=1.5, mae_r=-0.8, mfe_r=2.0)
    assert realized_r(Decision("LONG", 0.02), lbl) == 1.5
    assert realized_r(Decision("SHORT", 0.02), lbl) == -1.5
    assert realized_r(Decision("WAIT", 0.0), lbl) is None


def test_evaluate_reports_both_frames():
    labels = [PathLabel(ret_r=1.0, mae_r=-0.5, mfe_r=1.2) for _ in range(40)]
    decisions = [Decision("LONG", 0.01) for _ in range(40)]
    atr_fracs = [0.02] * 40
    fundings = [0.0] * 40
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=0.0, slippage_bps=0.0,
                            n_trials=10, trial_srs=[], drawdown_cap_r=15.0)
    assert res["risk_adjusted"]["trade_count"] == 40
    assert "dsr" in res["risk_adjusted"]
    assert "total_r" in res["fixed_cap"]
    assert "max_drawdown_r" in res["fixed_cap"]
    assert isinstance(res["fixed_cap"]["within_cap"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_evaluate.py -v`
Expected: FAIL (`equity_summary_from_returns` and module `evaluate` not found).

- [ ] **Step 3a: Refactor metrics.py**

In `src/moonface/research/metrics.py`, extract the equity walk and add a
returns-based summary. Add after the `EquitySummary` dataclass:

```python
def _equity_walk(returns: list[float]) -> tuple[float, float]:
    """Compound returns into (net_return, max_drawdown). Ruin (equity <= 0)
    clamps to (-1.0, -1.0)."""
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret in returns:
        equity *= 1.0 + ret
        if equity <= 0.0:
            return -1.0, -1.0
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    return equity - 1.0, max_dd


def equity_summary_from_returns(returns: list[float]) -> EquitySummary:
    """EquitySummary for an explicit, already-sized per-trade return stream
    (used by the path-signal evaluator where each trade carries its own
    conviction fraction)."""
    if not returns:
        return EquitySummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0)
    net, max_dd = _equity_walk(returns)
    if max_dd == 0.0:
        mar = math.inf if net > 0 else 0.0
    else:
        mar = net / abs(max_dd)
    return EquitySummary(
        trade_count=len(returns),
        net_return=round(net, 6),
        max_drawdown=round(max_dd, 6),
        mar=mar if math.isinf(mar) else round(mar, 4),
        sharpe=_sharpe(returns),
        skew=_skew(returns),
        kurtosis=_kurtosis(returns),
    )
```

Then make the existing `equity_summary` reuse the walk — replace its inline loop
(the block from `equity = 1.0` through the `net = equity - 1.0` assignment) with:

```python
    returns = [min(fraction, MAX_LEVERAGE * atr_frac) * r
               for r, atr_frac in trades]
    net, max_dd = _equity_walk(returns)
```

- [ ] **Step 3b: Verify the refactor did not change existing behavior**

Run: `python -m pytest tests/ -k metrics -v`
Expected: PASS (existing metrics tests still green).

- [ ] **Step 3c: Write the evaluator**

Create `src/moonface/research/pathsig/evaluate.py`:

```python
"""Score a decision stream under both risk frames.

risk_adjusted: each taken trade contributes a sized, leverage-clamped, net-of-
cost return; compounded into Sharpe/MAR/DSR (the primary frame).
fixed_cap: the same trades at unit size in R, summed, with the worst running R
drawdown checked against the prior program's absolute -15R cap (comparability)."""
from __future__ import annotations

from moonface.research.metrics import (MAX_LEVERAGE, deflated_sharpe,
                                        equity_summary_from_returns)
from moonface.research.pathsig.costs import apply_costs
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Decision


def realized_r(decision: Decision, label: PathLabel) -> float | None:
    """Terminal gross R in the chosen direction, held to horizon. None on WAIT."""
    if decision.action == "WAIT":
        return None
    return label.ret_r if decision.action == "LONG" else -label.ret_r


def evaluate_strategy(decisions: list[Decision], labels: list[PathLabel],
                      atr_fracs: list[float], fundings: list[float],
                      taker_bps: float, slippage_bps: float,
                      n_trials: int, trial_srs: list[float],
                      drawdown_cap_r: float) -> dict:
    sized_returns: list[float] = []
    r_stream: list[float] = []
    for d, lbl, af, fund in zip(decisions, labels, atr_fracs, fundings):
        gross = realized_r(d, lbl)
        if gross is None:
            continue
        net_r = apply_costs(gross, af, taker_bps, slippage_bps, fund)
        r_stream.append(net_r)
        f_eff = min(d.size, MAX_LEVERAGE * af)
        sized_returns.append(f_eff * net_r)

    eq = equity_summary_from_returns(sized_returns)
    dsr = deflated_sharpe(eq.sharpe, eq.trade_count, eq.skew, eq.kurtosis,
                          trial_srs, n_trials)

    total_r = round(sum(r_stream), 6)
    cum = 0.0
    peak = 0.0
    max_dd_r = 0.0
    for r in r_stream:
        cum += r
        peak = max(peak, cum)
        max_dd_r = min(max_dd_r, cum - peak)

    return {
        "risk_adjusted": {
            "trade_count": eq.trade_count,
            "net_return": eq.net_return,
            "max_drawdown": eq.max_drawdown,
            "mar": eq.mar,
            "sharpe": eq.sharpe,
            "dsr": dsr,
        },
        "fixed_cap": {
            "trade_count": len(r_stream),
            "total_r": total_r,
            "max_drawdown_r": round(max_dd_r, 6),
            "within_cap": abs(max_dd_r) <= drawdown_cap_r,
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_evaluate.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/metrics.py src/moonface/research/pathsig/evaluate.py tests/test_pathsig_evaluate.py
git commit -m "feat(pathsig): dual-frame evaluator + equity_summary_from_returns"
```

---

## Task 10: End-to-end smoke test with a trivial predictor

**Files:**
- Create: `src/moonface/research/pathsig/__init__.py` (append public re-exports)
- Test: `tests/test_pathsig_smoke.py`

Proves the whole pipeline runs: synthetic bundle → dataset → folds → a constant
predictor → policy → dual-frame evaluation, with no lookahead and a sane result.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_smoke.py
from moonface.models import Candle
from moonface.research.bundle import DataBundle
from moonface.research.pathsig.dataset import build_dataset
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.policy import Distribution, decide
from moonface.research.pathsig.walkforward import walk_forward_folds

H4 = 14_400_000


def _bundle(n):
    candles, funding, feat = [], [], []
    for i in range(n):
        price = 100.0 + 10.0 * (i % 50)  # cyclical, tradeable excursions
        candles.append(Candle(timestamp_ms=i * H4, open=price,
                              high=price * 1.02, low=price * 0.98,
                              close=price, volume=1.0))
        funding.append(0.0001)
        feat.append(1000.0 + i)
    return DataBundle(candles=candles, funding=funding, feature=feat)


def _daily(n):
    return [Candle(timestamp_ms=i * 86_400_000, open=100.0 + i, high=101.0 + i,
                  low=99.0 + i, close=100.0 + i, volume=1.0) for i in range(n)]


def test_pipeline_runs_end_to_end():
    bundle = _bundle(600)
    samples = build_dataset(bundle, h=6, atr_period=14,
                            xs_ret_rank=[0.5] * 600, xs_funding_rank=[0.5] * 600,
                            d1_candles=_daily(120), w1_candles=_daily(40))
    assert len(samples) > 50
    folds = walk_forward_folds(len(samples), n_folds=3, embargo=6,
                               lockbox_fraction=0.2)
    assert folds

    # constant "predictor": always mildly bullish -> exercises LONG + WAIT paths
    def predict(_x):
        return Distribution(p_up=0.55, exp_ret_r=0.3, exp_mae_r=-1.0,
                            exp_mfe_r=1.0)

    fold = folds[-1]
    decisions, labels, atr_fracs, fundings = [], [], [], []
    for pos in fold.test_idx:
        s = samples[pos]
        dist = predict(s.x)
        decisions.append(decide(dist, edge_threshold=0.2, kelly_scale=0.02,
                                max_fraction=0.02))
        labels.append(s.label)
        atr_fracs.append(s.x[4])   # atr_frac is FEATURE_NAMES index 4
        fundings.append(0.0)

    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=5.0, slippage_bps=2.0, n_trials=10,
                            trial_srs=[], drawdown_cap_r=15.0)
    assert res["risk_adjusted"]["trade_count"] >= 1
    assert 0.0 <= res["risk_adjusted"]["dsr"] <= 1.0
    assert isinstance(res["fixed_cap"]["within_cap"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_smoke.py -v`
Expected: FAIL only if `atr_frac` is not at index 4 — confirm against
`FEATURE_NAMES`. If the pipeline is incomplete it fails on import/attribute.

- [ ] **Step 3: Add public re-exports**

Append to `src/moonface/research/pathsig/__init__.py`:

```python
from moonface.research.pathsig.dataset import Sample, build_dataset
from moonface.research.pathsig.evaluate import evaluate_strategy, realized_r
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel, build_labels
from moonface.research.pathsig.policy import Decision, Distribution, decide
from moonface.research.pathsig.walkforward import Fold, walk_forward_folds

__all__ = [
    "Sample", "build_dataset", "evaluate_strategy", "realized_r",
    "FEATURE_NAMES", "PathLabel", "build_labels", "Decision", "Distribution",
    "decide", "Fold", "walk_forward_folds",
]
```

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest tests/ -q && ruff check src/moonface/research/pathsig tools/path_signal.py`
Expected: all tests PASS, ruff reports no errors.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/__init__.py tests/test_pathsig_smoke.py
git commit -m "feat(pathsig): end-to-end smoke test through trivial predictor"
```

---

## Task 11: Freeze the registration artifact

**Files:**
- Create: `experiments/path_signal/registration.json` (generated)

- [ ] **Step 1: Generate the frozen registration**

Run: `python tools/path_signal.py register`
Expected: writes `experiments/path_signal/registration.json` listing the 16
frozen feature names, horizons [6, 12], DSR threshold 0.95, lockbox 0.2.

- [ ] **Step 2: Verify contents**

Run: `python -m pytest tests/test_pathsig_register.py -v`
Expected: PASS.

- [ ] **Step 3: Commit (force-add — docs/experiments specs are tracked by convention despite global gitignore)**

```bash
git add -f experiments/path_signal/registration.json
git commit -m "chore(pathsig): freeze registration artifact"
```

---

## Self-Review

**Spec coverage** (against `docs/research-log/specs/2026-06-16-btc-distributional-path-signal-design.md`):
- §3.3 frozen feature set → Task 4 `FEATURE_NAMES` + Tasks 4–5 builders. ✅
- Label = forward path `(ret_r, mae_r, mfe_r)` → Task 2 reuses `event_outcome`. ✅
- §4 nested purged/embargoed walk-forward → Task 6 (folds + embargo + sealed tail). ✅ (Inner-CV hyperparameter selection belongs to the model plans, which run their grid *inside* each fold's `train_idx`; the harness exposes `train_idx`/`test_idx` for exactly that.)
- §4 DSR ≥ 0.95 with trial-count deflation → Task 9 passes `n_trials`/`trial_srs` to `deflated_sharpe`; the model plans supply the full grid count. ✅
- §4 cost model (taker + funding + slippage) → Task 7. ✅
- §4 one-touch lockbox tail → Task 6 excludes `lockbox_fraction`; opening it is a model-plan step using the existing `FencedBundle`. ✅
- Both risk frames → Task 9 `evaluate_strategy` returns `risk_adjusted` + `fixed_cap`. ✅
- §6 LONG/SHORT/WAIT translation + conviction sizing → Task 8 `decide`. ✅
- §2 pre-registration freeze → Tasks 1 + 11. ✅
- Rungs 1–3 (regime ensemble, gradient-boosted model, sequence model) → **out of scope, follow-on plans** (stated in scope note); this plan delivers the interfaces they consume: a predictor is `Callable[[list[float]], Distribution]`, training data is `Sample.x`/`Sample.label` over `Fold.train_idx`. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; commands have expected output. The Task 1 CLI imports `FEATURE_NAMES` from Task 4 — sequencing note added (register test verified green in Task 4). ✅

**Type consistency:** `Distribution`/`Decision` (Task 8) consumed unchanged by Task 9/10; `PathLabel` fields `ret_r/mae_r/mfe_r` consistent Tasks 2/5/9/10; `Sample.x` is the `FEATURE_NAMES`-ordered vector used everywhere; `atr_frac` is `FEATURE_NAMES` index 4, used as the cost denominator in Task 10's smoke test. `equity_summary_from_returns` defined in Task 9 and imported in Task 9's evaluator and test. ✅

---

## Follow-on plans (not in this plan)

1. **Rung 0/1 baseline plan** — replay the existing signal families as predictors through this harness; build the regime-weighted ensemble (B) that rung 2 must beat.
2. **Rung 2 model plan** — introduce the gradient-boosting/quantile dependency; train per-fold inside `Fold.train_idx` with inner CV; emit `Distribution`; run the full grid through the DSR deflation; open the lockbox once.
3. **Rung 3 plan (gated)** — sequence model, only if rung 2 clears the gate with residual capacity.
