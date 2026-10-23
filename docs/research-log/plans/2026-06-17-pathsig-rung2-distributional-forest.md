# Path Signal Rung-2 Distributional Forest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build rung-2 of the path-signal ladder — a from-scratch distributional random forest that emits a learned conditional path distribution per 4h bar, judged head-to-head against rung-0/rung-1 under the frozen deflated-Sharpe gate.

**Architecture:** A pure-numpy CART regression forest (`forest.py`) grown on `ret_r` variance reduction, with each leaf carrying its empirical `(ret_r, mae_r, mfe_r)` member set; predictions pool leaf members across trees into a `policy.Distribution` + return quantiles. A nested-CV harness (`rung2.py`) selects hyperparameters on an inner purged split, replays the model on the existing outer walk-forward folds with the unchanged `decide()` policy plus a quantile ruin clamp, and emits a verdict vs the rung-0 floor and rung-1 result. A `rung2` CLI subcommand mirrors the existing `ensemble` subcommand; the sealed lockbox tail is a separate, explicitly-gated step.

**Tech Stack:** Python 3, numpy (already present), pytest. Reuses `moonface.research.pathsig` (`policy`, `evaluate`, `costs`, `walkforward`, `data`, `baseline` constants) and `moonface.research.metrics.deflated_sharpe`.

**Spec:** `docs/research-log/specs/2026-06-17-pathsig-rung2-distributional-forest-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/moonface/research/pathsig/forest.py` | The DRF: regression-tree growth on `ret_r` variance, bagging, leaf member sets, `predict` → `Distribution` + quantiles. Pure numpy. Deterministic via seeded `numpy.default_rng`. |
| `src/moonface/research/pathsig/rung2.py` | Nested-CV harness: matrix builders, inner config selection, per-bar replay with ruin clamp, verdict vs rung-0/rung-1, doc builder, lockbox step. Mirrors `ensemble.py`. |
| `tools/path_signal.py` | Add the `rung2` subcommand + `--open-lockbox` (mirrors the `ensemble` subcommand). |
| `tests/test_pathsig_forest.py` | Unit tests for the tree/forest: split correctness, determinism, leaf pooling, quantile ordering, signal recovery. |
| `tests/test_pathsig_rung2.py` | Harness tests: matrix builders, inner-split no-leakage, config selection, ruin clamp, replay on learnable vs wall data, doc/verdict schema, lockbox. |
| `tests/test_pathsig_rung2_cli.py` | CLI wiring with injected offline readers. |

The frozen `FEATURE_NAMES` list and the lockbox boundary are **not** modified (pre-registration forbids feature changes without a version bump + fresh lockbox).

**Frozen constants (defined in `rung2.py`):**
- `STRUCTURE_GRID = [(d, m, mtry) for d in (3, 5) for m in (30, 60) for mtry in (4, 8)]` (8 configs)
- `EDGE_THRESHOLDS = (0.10, 0.20, 0.30)`
- `N_TREES = 200`
- `SEED = 12345`
- `RUIN_Q05_R = -3.0`  (zero size when the directional 5th-pct return is worse, in R)
- `INNER_TRAIN_FRAC = 0.7`
- `DSR_THRESHOLD = 0.95`
- reuse from `baseline`: `KELLY_SCALE`, `MAX_FRACTION`, `TAKER_BPS`, `SLIPPAGE_BPS`, `DRAWDOWN_CAP_R`, `LOCKBOX_FRACTION`, `ATR_PERIOD`, `POOL_SYMBOLS`

---

## Task 1: Best variance-reduction split

**Files:**
- Create: `src/moonface/research/pathsig/forest.py`
- Test: `tests/test_pathsig_forest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_forest.py
import numpy as np
import pytest

from moonface.research.pathsig.forest import _best_split


def test_best_split_finds_obvious_threshold():
    # feature 0 is a step: rows with x<5 -> y=0, x>=5 -> y=10
    X = np.array([[float(i)] for i in range(10)])
    y = np.array([0.0] * 5 + [10.0] * 5)
    rows = np.arange(10)
    split = _best_split(X, y, rows, feat_subset=np.array([0]), min_leaf=1)
    assert split is not None
    gain, feat, thr = split
    assert feat == 0
    assert 4.0 < thr < 5.0          # midpoint between x=4 and x=5
    assert gain == pytest.approx(250.0)   # parent SSE 250 -> 0 after split


def test_best_split_returns_none_when_no_valid_split():
    # min_leaf too large for any split to leave both sides populated
    X = np.array([[float(i)] for i in range(4)])
    y = np.array([0.0, 1.0, 2.0, 3.0])
    rows = np.arange(4)
    assert _best_split(X, y, rows, feat_subset=np.array([0]), min_leaf=3) is None


def test_best_split_skips_constant_feature():
    X = np.array([[1.0], [1.0], [1.0], [1.0]])
    y = np.array([0.0, 1.0, 2.0, 3.0])
    rows = np.arange(4)
    assert _best_split(X, y, rows, feat_subset=np.array([0]), min_leaf=1) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_forest.py -q`
Expected: FAIL — `ImportError: cannot import name '_best_split'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/research/pathsig/forest.py
"""From-scratch distributional random forest for the rung-2 path model.

A CART regression tree is grown to reduce the variance of ret_r; each leaf
retains the row indices of its members so the empirical (ret_r, mae_r, mfe_r)
distribution can be pooled across bagged trees at predict time. Pure numpy,
seeded for reproducibility (the one-touch lockbox depends on determinism).
Design frozen in docs/research-log/specs/2026-06-17-pathsig-rung2-distributional-forest-design.md."""
from __future__ import annotations

import numpy as np


def _best_split(X: np.ndarray, y: np.ndarray, rows: np.ndarray,
                feat_subset: np.ndarray, min_leaf: int):
    """Best (gain, feature, threshold) by ret_r SSE reduction over `rows`,
    considering only `feat_subset`. None when no split leaves >= min_leaf on
    both sides. Gain is parent SSE minus summed child SSE (>= 0)."""
    n = rows.shape[0]
    if n < 2 * min_leaf:
        return None
    yr = y[rows]
    total_sum = float(yr.sum())
    total_sq = float((yr * yr).sum())
    parent_sse = total_sq - total_sum * total_sum / n
    best = None
    for f in feat_subset:
        xf = X[rows, f]
        order = np.argsort(xf, kind="stable")
        xs = xf[order]
        ys = yr[order]
        csum = np.cumsum(ys)
        csq = np.cumsum(ys * ys)
        nl = np.arange(1, n)                      # left size after position k
        nr = n - nl
        ls = csum[:-1]
        lsq = csq[:-1]
        rs = total_sum - ls
        rsq = total_sq - lsq
        sse = (lsq - ls * ls / nl) + (rsq - rs * rs / nr)
        valid = (nl >= min_leaf) & (nr >= min_leaf) & (xs[:-1] != xs[1:])
        if not valid.any():
            continue
        sse = np.where(valid, sse, np.inf)
        k = int(np.argmin(sse))
        gain = parent_sse - float(sse[k])
        if best is None or gain > best[0]:
            thr = (float(xs[k]) + float(xs[k + 1])) / 2.0
            best = (gain, int(f), thr)
    return best
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_forest.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/forest.py tests/test_pathsig_forest.py
git commit -m "feat(pathsig): rung-2 forest variance-reduction split"
```

---

## Task 2: Grow a single regression tree with leaf member sets

**Files:**
- Modify: `src/moonface/research/pathsig/forest.py`
- Test: `tests/test_pathsig_forest.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_forest.py
from moonface.research.pathsig.forest import _grow_tree, _leaf_rows


def test_grow_tree_separates_and_leaf_rows_route():
    X = np.array([[float(i)] for i in range(20)])
    y = np.array([0.0] * 10 + [10.0] * 10)
    rng = np.random.default_rng(0)
    tree = _grow_tree(X, y, np.arange(20), max_depth=3, min_leaf=1,
                      mtry=1, rng=rng)
    low = _leaf_rows(tree, np.array([1.0]))
    high = _leaf_rows(tree, np.array([18.0]))
    assert set(low.tolist()).issubset(set(range(10)))
    assert set(high.tolist()).issubset(set(range(10, 20)))


def test_grow_tree_depth_zero_is_single_leaf():
    X = np.array([[float(i)] for i in range(8)])
    y = np.arange(8, dtype=float)
    rng = np.random.default_rng(0)
    tree = _grow_tree(X, y, np.arange(8), max_depth=0, min_leaf=1,
                      mtry=1, rng=rng)
    assert tree.feature == -1                       # leaf
    assert sorted(_leaf_rows(tree, np.array([3.0])).tolist()) == list(range(8))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_forest.py -k "grow_tree" -q`
Expected: FAIL — `cannot import name '_grow_tree'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/forest.py (after _best_split)
from dataclasses import dataclass


@dataclass
class _Node:
    feature: int                 # split feature index, -1 for a leaf
    threshold: float
    left: "_Node | None"
    right: "_Node | None"
    rows: np.ndarray | None      # member row indices, set only on leaves


def _make_leaf(rows: np.ndarray) -> _Node:
    return _Node(feature=-1, threshold=0.0, left=None, right=None, rows=rows)


def _grow_tree(X: np.ndarray, y: np.ndarray, rows: np.ndarray, *,
               max_depth: int, min_leaf: int, mtry: int,
               rng: np.random.Generator, depth: int = 0) -> _Node:
    """Recursively grow a CART regression tree on ret_r (=y). Leaves keep their
    member row indices. A node becomes a leaf at max_depth, when too small to
    split, or when no split improves SSE."""
    if depth >= max_depth or rows.shape[0] < 2 * min_leaf:
        return _make_leaf(rows)
    n_features = X.shape[1]
    k = min(mtry, n_features)
    feat_subset = rng.choice(n_features, size=k, replace=False)
    split = _best_split(X, y, rows, feat_subset, min_leaf)
    if split is None:
        return _make_leaf(rows)
    _, feat, thr = split
    mask = X[rows, feat] <= thr
    left_rows = rows[mask]
    right_rows = rows[~mask]
    if left_rows.shape[0] < min_leaf or right_rows.shape[0] < min_leaf:
        return _make_leaf(rows)
    left = _grow_tree(X, y, left_rows, max_depth=max_depth, min_leaf=min_leaf,
                      mtry=mtry, rng=rng, depth=depth + 1)
    right = _grow_tree(X, y, right_rows, max_depth=max_depth, min_leaf=min_leaf,
                       mtry=mtry, rng=rng, depth=depth + 1)
    return _Node(feature=feat, threshold=thr, left=left, right=right, rows=None)


def _leaf_rows(node: _Node, x: np.ndarray) -> np.ndarray:
    """Route a single feature vector x to its leaf and return member rows."""
    while node.feature != -1:
        node = node.left if x[node.feature] <= node.threshold else node.right
    return node.rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_forest.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/forest.py tests/test_pathsig_forest.py
git commit -m "feat(pathsig): rung-2 regression tree with leaf member sets"
```

---

## Task 3: DistForest — bagging, pooled prediction, determinism

**Files:**
- Modify: `src/moonface/research/pathsig/forest.py`
- Test: `tests/test_pathsig_forest.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_forest.py
from moonface.research.pathsig.forest import DistForest, PathPrediction
from moonface.research.pathsig.policy import Distribution


def _labels(rets):
    # labels matrix (n,3): ret_r, mae_r (<=0), mfe_r (>=0)
    return np.array([[r, -abs(r) - 0.5, abs(r) + 0.5] for r in rets])


def test_forest_predicts_directional_distribution():
    # feature 0 < 0 -> negative ret, > 0 -> positive ret
    X = np.array([[float(i - 25)] for i in range(50)])
    rets = [-1.0 if i < 25 else 1.0 for i in range(50)]
    forest = DistForest(n_trees=25, max_depth=3, min_leaf=2, mtry=1, seed=1)
    forest.fit(X, _labels(rets))
    up = forest.predict(np.array([20.0]))
    down = forest.predict(np.array([-20.0]))
    assert isinstance(up, PathPrediction)
    assert isinstance(up.dist, Distribution)
    assert up.dist.exp_ret_r > 0 and up.dist.p_up > 0.5
    assert down.dist.exp_ret_r < 0 and down.dist.p_up < 0.5


def test_forest_is_deterministic_for_a_seed():
    X = np.array([[float(i)] for i in range(40)])
    labels = _labels([float(i % 3 - 1) for i in range(40)])
    a = DistForest(n_trees=10, max_depth=2, min_leaf=2, mtry=1, seed=7)
    b = DistForest(n_trees=10, max_depth=2, min_leaf=2, mtry=1, seed=7)
    a.fit(X, labels)
    b.fit(X, labels)
    pa, pb = a.predict(np.array([5.0])), b.predict(np.array([5.0]))
    assert pa.dist == pb.dist and pa.q05 == pb.q05 and pa.q95 == pb.q95


def test_forest_quantiles_are_ordered():
    X = np.array([[float(i)] for i in range(40)])
    labels = _labels([float(i - 20) for i in range(40)])
    f = DistForest(n_trees=10, max_depth=3, min_leaf=2, mtry=1, seed=3)
    f.fit(X, labels)
    p = f.predict(np.array([10.0]))
    assert p.q05 <= p.q50 <= p.q95
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_forest.py -k "forest" -q`
Expected: FAIL — `cannot import name 'DistForest'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/forest.py
from moonface.research.pathsig.policy import Distribution


@dataclass(frozen=True)
class PathPrediction:
    dist: Distribution
    q05: float
    q50: float
    q95: float


class DistForest:
    """Bagged regression trees on ret_r; predicts a pooled empirical path
    distribution. Trees train on bootstrap resamples with per-split feature
    subsampling; all randomness comes from one seeded Generator."""

    def __init__(self, *, n_trees: int, max_depth: int, min_leaf: int,
                 mtry: int, seed: int):
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.mtry = mtry
        self.seed = seed
        self._trees: list[_Node] = []
        self._labels: np.ndarray | None = None

    def fit(self, X: np.ndarray, labels: np.ndarray) -> "DistForest":
        """X: (n, n_features). labels: (n, 3) = ret_r, mae_r, mfe_r."""
        self._labels = labels
        y = labels[:, 0]
        n = X.shape[0]
        rng = np.random.default_rng(self.seed)
        self._trees = []
        for _ in range(self.n_trees):
            boot = rng.integers(0, n, size=n)        # bootstrap row indices
            self._trees.append(
                _grow_tree(X, y, boot, max_depth=self.max_depth,
                           min_leaf=self.min_leaf, mtry=self.mtry, rng=rng))
        return self

    def predict(self, x: np.ndarray) -> PathPrediction:
        pooled: list[int] = []
        for tree in self._trees:
            pooled.extend(_leaf_rows(tree, x).tolist())
        members = self._labels[np.asarray(pooled, dtype=int)]
        rets = members[:, 0]
        dist = Distribution(
            p_up=float((rets > 0).mean()),
            exp_ret_r=float(rets.mean()),
            exp_mae_r=float(members[:, 1].mean()),
            exp_mfe_r=float(members[:, 2].mean()))
        q05, q50, q95 = (float(v) for v in np.quantile(rets, [0.05, 0.5, 0.95]))
        return PathPrediction(dist=dist, q05=q05, q50=q50, q95=q95)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_forest.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/forest.py tests/test_pathsig_forest.py
git commit -m "feat(pathsig): rung-2 bagged distributional forest"
```

---

## Task 4: Matrix builders + ruin clamp

**Files:**
- Create: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_rung2.py
import numpy as np
import pytest

from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Decision
from moonface.research.pathsig.forest import PathPrediction
from moonface.research.pathsig.policy import Distribution
from moonface.research.pathsig.rung2 import (X_matrix, labels_matrix,
                                             ruin_clamp, RUIN_Q05_R)

_ATR = FEATURE_NAMES.index("atr_frac")


def _sample(index, feat0=0.0, ret=0.0):
    x = [0.0] * len(FEATURE_NAMES)
    x[0] = feat0
    x[_ATR] = 0.02
    return Sample(index=index, timestamp_ms=index, x=x,
                  label=PathLabel(ret_r=ret, mae_r=-1.0, mfe_r=1.0))


def test_matrix_builders_shapes_and_order():
    samples = [_sample(i, feat0=float(i), ret=float(i) / 10.0) for i in range(5)]
    pos = [0, 2, 4]
    X = X_matrix(samples, pos)
    L = labels_matrix(samples, pos)
    assert X.shape == (3, len(FEATURE_NAMES))
    assert L.shape == (3, 3)
    assert X[1, 0] == 2.0                      # second selected sample's feat0
    assert L[2, 0] == pytest.approx(0.4)       # ret of sample index 4


def test_ruin_clamp_zeroes_dangerous_long():
    pred = PathPrediction(dist=Distribution(0.6, 1.0, -1.0, 2.0),
                          q05=RUIN_Q05_R - 1.0, q50=0.0, q95=2.0)
    clamped = ruin_clamp(Decision("LONG", 0.01), pred)
    assert clamped == Decision("WAIT", 0.0)


def test_ruin_clamp_passes_safe_trade():
    pred = PathPrediction(dist=Distribution(0.6, 1.0, -1.0, 2.0),
                          q05=RUIN_Q05_R + 1.0, q50=0.0, q95=2.0)
    dec = Decision("LONG", 0.01)
    assert ruin_clamp(dec, pred) == dec


def test_ruin_clamp_uses_negative_q95_for_short():
    # for a SHORT, the adverse tail is the upper return tail (-q95)
    pred = PathPrediction(dist=Distribution(0.4, -1.0, -1.0, 2.0),
                          q05=0.0, q50=0.0, q95=-RUIN_Q05_R + 1.0)
    assert ruin_clamp(Decision("SHORT", 0.01), pred) == Decision("WAIT", 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: FAIL — `cannot import name 'X_matrix'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/research/pathsig/rung2.py
"""Rung-2 distributional random forest harness.

Builds feature/label matrices from the shared Sample grid, selects forest
hyperparameters on an inner purged split, replays the forest on the existing
outer walk-forward folds with the unchanged decide() policy plus a quantile
ruin clamp, and scores the OOS stream under both risk frames. Verdict is
head-to-head against the rung-0 floor and the rung-1 result.
Design frozen in docs/research-log/specs/2026-06-17-pathsig-rung2-distributional-forest-design.md."""
from __future__ import annotations

import numpy as np

from moonface.research.pathsig.baseline import (
    ATR_PERIOD, DRAWDOWN_CAP_R, KELLY_SCALE, LOCKBOX_FRACTION, MAX_FRACTION,
    POOL_SYMBOLS, SLIPPAGE_BPS, TAKER_BPS)
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.forest import DistForest, PathPrediction
from moonface.research.pathsig.policy import Decision

_ATR_IDX = FEATURE_NAMES.index("atr_frac")

# Frozen rung-2 hyperparameter grid and run constants.
STRUCTURE_GRID = [(d, m, mtry) for d in (3, 5) for m in (30, 60)
                  for mtry in (4, 8)]                       # 8 configs
EDGE_THRESHOLDS = (0.10, 0.20, 0.30)
N_TREES = 200
SEED = 12345
RUIN_Q05_R = -3.0
INNER_TRAIN_FRAC = 0.7
DSR_THRESHOLD = 0.95


def X_matrix(samples: list[Sample], positions: list[int]) -> np.ndarray:
    """(k, n_features) feature matrix for the given sample positions."""
    return np.array([samples[p].x for p in positions], dtype=float)


def labels_matrix(samples: list[Sample], positions: list[int]) -> np.ndarray:
    """(k, 3) label matrix: ret_r, mae_r, mfe_r for the given positions."""
    return np.array([[samples[p].label.ret_r, samples[p].label.mae_r,
                      samples[p].label.mfe_r] for p in positions], dtype=float)


def ruin_clamp(decision: Decision, pred: PathPrediction) -> Decision:
    """Zero a trade whose directional 5th-percentile return is worse than the
    frozen ruin floor. LONG adverse tail = q05; SHORT adverse tail = -q95."""
    if decision.action == "WAIT":
        return decision
    adverse = pred.q05 if decision.action == "LONG" else -pred.q95
    if adverse < RUIN_Q05_R:
        return Decision("WAIT", 0.0)
    return decision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 matrix builders and ruin clamp"
```

---

## Task 5: Fit a forest config and replay a decision stream over positions

**Files:**
- Modify: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

This adds `fit_config` (train a forest for one `(structure, threshold)`) and
`replay_positions` (decide on a set of test positions, returning sized result
via the shared evaluator).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_rung2.py
from moonface.research.pathsig.rung2 import fit_config, replay_positions


def _learnable(n=400):
    # feat0 sign predicts ret sign; mae/mfe symmetric, atr fixed
    samples = []
    rng = np.random.default_rng(0)
    for i in range(n):
        f0 = float(rng.normal())
        ret = 1.0 if f0 > 0 else -1.0
        x = [0.0] * len(FEATURE_NAMES)
        x[0] = f0
        x[_ATR] = 0.02
        samples.append(Sample(index=i, timestamp_ms=i, x=x,
                              label=PathLabel(ret_r=ret, mae_r=-0.5, mfe_r=1.5)))
    return samples


def test_fit_config_predicts_learnable_sign():
    samples = _learnable(400)
    forest = fit_config(samples, list(range(400)), structure=(5, 30, 4))
    x = np.array(samples[0].x)
    x[0] = 3.0
    assert forest.predict(x).dist.exp_ret_r > 0


def test_replay_positions_trades_learnable_and_scores():
    samples = _learnable(400)
    forest = fit_config(samples, list(range(300)), structure=(5, 30, 4))
    res = replay_positions(samples, list(range(300, 400)), forest,
                           edge_threshold=0.10, n_trials=1, trial_srs=[])
    assert res["status"] == "ok"
    assert res["n_trades"] > 0
    assert res["fixed_cap"]["total_r"] > 0      # positive on a learnable signal


def test_replay_positions_no_trades_when_threshold_too_high():
    samples = _learnable(200)
    forest = fit_config(samples, list(range(150)), structure=(3, 60, 4))
    res = replay_positions(samples, list(range(150, 200)), forest,
                           edge_threshold=100.0, n_trials=1, trial_srs=[])
    assert res["status"] == "no_trades"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -k "fit_config or replay_positions" -q`
Expected: FAIL — `cannot import name 'fit_config'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/rung2.py
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.policy import decide


def fit_config(samples: list[Sample], train_pos: list[int],
               structure: tuple[int, int, int]) -> DistForest:
    """Train a DistForest for one (max_depth, min_leaf, mtry) config on the
    given training positions. ret_r is the split target; the full label matrix
    feeds the leaf distributions."""
    max_depth, min_leaf, mtry = structure
    X = X_matrix(samples, train_pos)
    L = labels_matrix(samples, train_pos)
    return DistForest(n_trees=N_TREES, max_depth=max_depth, min_leaf=min_leaf,
                      mtry=mtry, seed=SEED).fit(X, L)


def replay_positions(samples: list[Sample], test_pos: list[int],
                     forest: DistForest, *, edge_threshold: float,
                     n_trials: int, trial_srs: list[float]) -> dict:
    """Decide on every test position from the forest's distribution (LONG-frame
    labels, so decide()'s LONG/SHORT map straight onto realized_r), apply the
    ruin clamp, and score the stream under both risk frames."""
    decisions, labels, atr_fracs, fundings = [], [], [], []
    for p in test_pos:
        pred = forest.predict(np.array(samples[p].x, dtype=float))
        dec = decide(pred.dist, edge_threshold, KELLY_SCALE, MAX_FRACTION)
        dec = ruin_clamp(dec, pred)
        decisions.append(dec)
        labels.append(samples[p].label)
        atr_fracs.append(samples[p].x[_ATR_IDX])
        fundings.append(0.0)
    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    if n_trades == 0:
        return {"status": "no_trades", "n_events": len(decisions), "n_trades": 0}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=TAKER_BPS, slippage_bps=SLIPPAGE_BPS,
                            n_trials=n_trials, trial_srs=trial_srs,
                            drawdown_cap_r=DRAWDOWN_CAP_R)
    return {"status": "ok", "n_events": len(decisions), "n_trades": n_trades,
            **res}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 forest fit and decision replay"
```

---

## Task 6: Inner-split hyperparameter selection (no leakage)

**Files:**
- Modify: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

`inner_split` carves a purged/embargoed inner train/test from an outer train
block. `select_config` fits every `(structure, threshold)` on inner-train, scores
on inner-test, and returns the best plus the list of inner Sharpes (trial_srs).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_rung2.py
from moonface.research.pathsig.rung2 import (inner_split, select_config,
                                             STRUCTURE_GRID, EDGE_THRESHOLDS)


def test_inner_split_purges_and_is_disjoint():
    train = list(range(100))
    inner_train, inner_test = inner_split(train, embargo=6)
    assert set(inner_train).isdisjoint(inner_test)
    assert max(inner_train) + 6 <= min(inner_test)      # embargo gap respected
    assert inner_test[-1] == 99                          # inner test is the tail


def test_select_config_returns_grid_member_and_trial_srs():
    samples = _learnable(400)
    choice = select_config(samples, list(range(400)), embargo=6)
    assert choice.structure in STRUCTURE_GRID
    assert choice.edge_threshold in EDGE_THRESHOLDS
    # every (structure, threshold) that produced trades contributes a trial SR
    assert len(choice.trial_srs) >= 1
    assert len(choice.trial_srs) <= len(STRUCTURE_GRID) * len(EDGE_THRESHOLDS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -k "inner_split or select_config" -q`
Expected: FAIL — `cannot import name 'inner_split'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/rung2.py
from dataclasses import dataclass


def inner_split(train_pos: list[int], embargo: int) -> tuple[list[int], list[int]]:
    """Carve a purged inner train/test from a contiguous outer train block.
    Inner test is the final (1 - INNER_TRAIN_FRAC) of the block; an embargo gap
    is removed from the end of inner train so horizon labels cannot leak."""
    n = len(train_pos)
    cut = int(n * INNER_TRAIN_FRAC)
    inner_train = train_pos[:max(0, cut - embargo)]
    inner_test = train_pos[cut:]
    return inner_train, inner_test


@dataclass(frozen=True)
class ConfigChoice:
    structure: tuple[int, int, int]
    edge_threshold: float
    trial_srs: list[float]


def select_config(samples: list[Sample], train_pos: list[int],
                  embargo: int) -> ConfigChoice:
    """Pick the (structure, edge_threshold) with the best inner-test Sharpe.
    Returns the choice plus every evaluated config's inner Sharpe (trial_srs for
    the deflation). Falls back to the first grid config if nothing trades."""
    inner_train, inner_test = inner_split(train_pos, embargo)
    trial_srs: list[float] = []
    best = None                                  # (sharpe, structure, threshold)
    for structure in STRUCTURE_GRID:
        forest = fit_config(samples, inner_train, structure)
        for et in EDGE_THRESHOLDS:
            res = replay_positions(samples, inner_test, forest,
                                   edge_threshold=et, n_trials=1, trial_srs=[])
            if res["status"] != "ok":
                continue
            sr = res["risk_adjusted"]["sharpe"]
            trial_srs.append(sr)
            if best is None or sr > best[0]:
                best = (sr, structure, et)
    if best is None:
        return ConfigChoice(structure=STRUCTURE_GRID[0],
                            edge_threshold=EDGE_THRESHOLDS[0], trial_srs=[])
    return ConfigChoice(structure=best[1], edge_threshold=best[2],
                        trial_srs=trial_srs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 inner-CV hyperparameter selection"
```

---

## Task 7: Outer-fold replay (nested CV)

**Files:**
- Modify: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

`replay_forest` runs the full nested loop: per outer fold, select a config on the
train block, refit on the whole train block, decide on the test block, then score
the concatenated OOS stream with the deflation trial count.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_rung2.py
from moonface.research.pathsig.rung2 import replay_forest
from moonface.research.pathsig.walkforward import walk_forward_folds


def test_replay_forest_runs_nested_and_scores_learnable():
    samples = _learnable(600)
    folds = walk_forward_folds(len(samples), n_folds=2, embargo=6,
                               lockbox_fraction=0.2)
    res = replay_forest(samples, folds, h=6, n_trials=48)
    assert res["status"] == "ok"
    assert res["n_trades"] > 0
    assert "selected" in res and len(res["selected"]) == len(folds)


def test_replay_forest_no_folds_is_no_trades():
    samples = _learnable(50)
    res = replay_forest(samples, [], h=6, n_trials=48)
    assert res["status"] == "no_trades"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -k "replay_forest" -q`
Expected: FAIL — `cannot import name 'replay_forest'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/rung2.py
from moonface.research.pathsig.walkforward import Fold


def replay_forest(samples: list[Sample], folds: list[Fold], *, h: int,
                  n_trials: int) -> dict:
    """Nested walk-forward: per fold select a config on the train block, refit
    on the full train block, decide on every test bar, and score the pooled OOS
    stream. trial_srs is the union of all folds' inner Sharpes."""
    decisions, labels, atr_fracs, fundings = [], [], [], []
    selected: list[dict] = []
    trial_srs: list[float] = []
    for fold in folds:
        choice = select_config(samples, fold.train_idx, embargo=h)
        trial_srs.extend(choice.trial_srs)
        forest = fit_config(samples, fold.train_idx, choice.structure)
        for p in fold.test_idx:
            pred = forest.predict(np.array(samples[p].x, dtype=float))
            dec = decide(pred.dist, choice.edge_threshold, KELLY_SCALE,
                         MAX_FRACTION)
            dec = ruin_clamp(dec, pred)
            decisions.append(dec)
            labels.append(samples[p].label)
            atr_fracs.append(samples[p].x[_ATR_IDX])
            fundings.append(0.0)
        selected.append({"structure": list(choice.structure),
                         "edge_threshold": choice.edge_threshold})

    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    if n_trades == 0:
        return {"status": "no_trades", "n_events": len(decisions),
                "n_trades": 0, "selected": selected}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=TAKER_BPS, slippage_bps=SLIPPAGE_BPS,
                            n_trials=n_trials, trial_srs=trial_srs,
                            drawdown_cap_r=DRAWDOWN_CAP_R)
    return {"status": "ok", "n_events": len(decisions), "n_trades": n_trades,
            "selected": selected, **res}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (11 tests). (This test trains forests; expect a few seconds.)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 nested walk-forward replay"
```

---

## Task 8: Verdict vs rung-0 floor and rung-1

**Files:**
- Modify: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_rung2.py
from moonface.research.pathsig.rung2 import (rung2_verdict, _rung0_floor,
                                             _rung1_result)


def _ok_result(total_r, dsr):
    return {"status": "ok", "h": 6,
            "fixed_cap": {"total_r": total_r, "max_drawdown_r": -5.0,
                          "within_cap": True},
            "risk_adjusted": {"sharpe": 0.2, "dsr": dsr, "mar": 0.3}}


def test_rung0_floor_and_rung1_lookup_by_horizon():
    rung0 = {"rows": [
        {"family": "a", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 9.3}, "risk_adjusted": {"dsr": 0.0}},
        {"family": "b", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 4.0}, "risk_adjusted": {"dsr": 0.0}}]}
    assert _rung0_floor(rung0, 6)["best_total_r"] == 9.3
    rung1 = {"rung1": [{"status": "ok", "h": 6,
                        "fixed_cap": {"total_r": -22.0},
                        "risk_adjusted": {"dsr": 0.0}}]}
    assert _rung1_result(rung1, 6)["fixed_cap"]["total_r"] == -22.0


def test_verdict_requires_beating_both_and_gate():
    result = _ok_result(total_r=30.0, dsr=0.96)
    v = rung2_verdict(result, floor={"best_total_r": 9.3},
                      rung1={"fixed_cap": {"total_r": -22.0},
                             "risk_adjusted": {"dsr": 0.0}})
    assert v["beats_rung0"] and v["beats_rung1"] and v["clears_gate"]

    weak = _ok_result(total_r=5.0, dsr=0.50)
    v2 = rung2_verdict(weak, floor={"best_total_r": 9.3},
                       rung1={"fixed_cap": {"total_r": -22.0},
                              "risk_adjusted": {"dsr": 0.0}})
    assert v2["beats_rung0"] is False and v2["clears_gate"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -k "verdict or floor or rung1_lookup" -q`
Expected: FAIL — `cannot import name 'rung2_verdict'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/rung2.py
def _rung0_floor(rung0_doc: dict | None, h: int) -> dict | None:
    if not rung0_doc:
        return None
    ok = [r for r in rung0_doc.get("rows", [])
          if r.get("status") == "ok" and r.get("h") == h]
    if not ok:
        return None
    best = max(ok, key=lambda r: r["fixed_cap"]["total_r"])
    return {"best_total_r": best["fixed_cap"]["total_r"],
            "best_family": best["family"], "best_params": best["params"]}


def _rung1_result(rung1_doc: dict | None, h: int) -> dict | None:
    if not rung1_doc:
        return None
    for r in rung1_doc.get("rung1", []):
        if r.get("status") == "ok" and r.get("h") == h:
            return r
    return None


def rung2_verdict(result: dict, floor: dict | None,
                  rung1: dict | None) -> dict:
    """Success = beats the rung-0 floor AND the rung-1 result on fixed-cap
    total_r (and not worse on risk-adjusted DSR) AND clears the DSR gate."""
    if result.get("status") != "ok":
        return {"h": result.get("h"), "beats_rung0": False, "beats_rung1": False,
                "clears_gate": False, "note": "forest produced no trades"}
    total_r = result["fixed_cap"]["total_r"]
    dsr = result["risk_adjusted"]["dsr"]
    beats0 = floor is None or total_r > floor["best_total_r"]
    beats1 = (rung1 is None or rung1.get("status") != "ok"
              or total_r > rung1["fixed_cap"]["total_r"])
    clears = dsr >= DSR_THRESHOLD
    if clears and beats0 and beats1:
        note = "forest beats rung-1 and rung-0 AND clears the DSR gate"
    elif beats0 and beats1:
        note = "path model helps but is not deflation-significant"
    else:
        note = "forest does not beat the rungs below it"
    return {"h": result.get("h"), "beats_rung0": beats0, "beats_rung1": beats1,
            "clears_gate": clears, "note": note}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 head-to-head verdict"
```

---

## Task 9: Doc builder (`run_rung2_to_doc`)

**Files:**
- Modify: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_rung2.py
from moonface.models import Candle
from moonface.research.pathsig.rung2 import run_rung2_to_doc

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_run_rung2_to_doc_schema_and_verdict():
    rung0 = {"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}
    rung1 = {"rung1": [{"status": "ok", "h": 6,
                        "fixed_cap": {"total_r": -22.0, "max_drawdown_r": -64.0,
                                      "within_cap": False},
                        "risk_adjusted": {"sharpe": 0.0, "dsr": 0.0, "mar": -0.1}}]}
    doc = run_rung2_to_doc(_readers(500), n_folds=2, horizons=[6],
                           pool_symbols=["ETHUSDT"], rung0_doc=rung0,
                           rung1_doc=rung1)
    assert doc["config"]["horizons"] == [6]
    assert doc["config"]["n_trials"] == len(STRUCTURE_GRID) * len(EDGE_THRESHOLDS)
    r2 = doc["rung2"][0]
    assert r2["h"] == 6 and r2["status"] in {"ok", "no_trades"}
    v = doc["verdict"][0]
    assert isinstance(v["beats_rung0"], bool)
    assert isinstance(v["beats_rung1"], bool)
    assert isinstance(v["clears_gate"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -k "run_rung2_to_doc" -q`
Expected: FAIL — `cannot import name 'run_rung2_to_doc'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/rung2.py
from moonface.research.pathsig.data import build_btc_dataset


def run_rung2_to_doc(readers: dict, *, n_folds: int, horizons: list[int],
                     pool_symbols: list[str] = POOL_SYMBOLS,
                     deploy: str = "BTCUSDT", rung0_doc: dict | None = None,
                     rung1_doc: dict | None = None) -> dict:
    """Full rung-2 results document from injectable readers (offline testable).
    One result + verdict per horizon. n_trials = |structure| x |thresholds| x
    |horizons| (deflation budget), passed identically to every horizon."""
    n_trials = len(STRUCTURE_GRID) * len(EDGE_THRESHOLDS) * len(horizons)
    rung2, verdict = [], []
    for h in horizons:
        _, samples = build_btc_dataset(readers, h=h, atr_period=ATR_PERIOD,
                                       pool_symbols=pool_symbols, deploy=deploy)
        folds = walk_forward_folds(len(samples), n_folds=n_folds, embargo=h,
                                   lockbox_fraction=LOCKBOX_FRACTION)
        res = replay_forest(samples, folds, h=h, n_trials=n_trials)
        res["h"] = h
        rung2.append(res)
        verdict.append(rung2_verdict(res, _rung0_floor(rung0_doc, h),
                                     _rung1_result(rung1_doc, h)))
    return {
        "config": {
            "deploy": deploy, "horizons": horizons, "n_folds": n_folds,
            "lockbox_fraction": LOCKBOX_FRACTION, "atr_period": ATR_PERIOD,
            "n_trees": N_TREES, "structure_grid": [list(s) for s in STRUCTURE_GRID],
            "edge_thresholds": list(EDGE_THRESHOLDS), "seed": SEED,
            "ruin_q05_r": RUIN_Q05_R, "kelly_scale": KELLY_SCALE,
            "max_fraction": MAX_FRACTION, "taker_bps": TAKER_BPS,
            "slippage_bps": SLIPPAGE_BPS, "drawdown_cap_r": DRAWDOWN_CAP_R,
            "dsr_threshold": DSR_THRESHOLD, "n_trials": n_trials,
            "pool_symbols": pool_symbols,
        },
        "rung2": rung2,
        "rung0_floor": {h: _rung0_floor(rung0_doc, h) for h in horizons},
        "verdict": verdict,
    }
```

Add the import for `walk_forward_folds` at the top of the module (next to the
existing `Fold` import):

```python
from moonface.research.pathsig.walkforward import Fold, walk_forward_folds
```

(Remove the now-duplicate `from ... import Fold` line added in Task 7 if it is
separate — keep a single combined import.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (14 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 results document builder"
```

---

## Task 10: Lockbox step (one-touch, gated)

**Files:**
- Modify: `src/moonface/research/pathsig/rung2.py`
- Test: `tests/test_pathsig_rung2.py`

`open_lockbox` selects a config on all usable (non-lockbox) data, refits on it,
and scores the sealed tail exactly once.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pathsig_rung2.py
from moonface.research.pathsig.rung2 import open_lockbox


def test_open_lockbox_scores_only_the_tail():
    samples = _learnable(600)
    res = open_lockbox(samples, h=6, n_trials=48)
    assert res["status"] in {"ok", "no_trades"}
    # tail size = total minus usable (1 - lockbox_fraction)
    usable = int(len(samples) * (1.0 - 0.2))
    assert res["n_events"] == len(samples) - usable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2.py -k "open_lockbox" -q`
Expected: FAIL — `cannot import name 'open_lockbox'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/moonface/research/pathsig/rung2.py
def open_lockbox(samples: list[Sample], *, h: int, n_trials: int) -> dict:
    """One-touch sealed-tail evaluation. Select a config via inner CV on all
    usable (non-lockbox) data, refit on all usable data, and score the sealed
    final lockbox_fraction tail exactly once. Run only after OOS success."""
    n = len(samples)
    usable = int(n * (1.0 - LOCKBOX_FRACTION))
    train_pos = list(range(usable))
    tail_pos = list(range(usable, n))
    choice = select_config(samples, train_pos, embargo=h)
    forest = fit_config(samples, train_pos, choice.structure)
    res = replay_positions(samples, tail_pos, forest,
                           edge_threshold=choice.edge_threshold,
                           n_trials=n_trials, trial_srs=choice.trial_srs)
    res["h"] = h
    res["selected"] = {"structure": list(choice.structure),
                       "edge_threshold": choice.edge_threshold}
    return res
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2.py -q`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/rung2.py tests/test_pathsig_rung2.py
git commit -m "feat(pathsig): rung-2 one-touch lockbox step"
```

---

## Task 11: CLI `rung2` subcommand

**Files:**
- Modify: `tools/path_signal.py`
- Test: `tests/test_pathsig_rung2_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_rung2_cli.py
import json
import sys
from pathlib import Path

from moonface.models import Candle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import path_signal  # noqa: E402

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_rung2_writes_results_json(tmp_path):
    rung0 = tmp_path / "rung0.json"
    rung0.write_text(json.dumps({"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}))
    rung1 = tmp_path / "rung1.json"
    rung1.write_text(json.dumps({"rung1": [
        {"status": "ok", "h": 6,
         "fixed_cap": {"total_r": -22.0, "max_drawdown_r": -64.0, "within_cap": False},
         "risk_adjusted": {"sharpe": 0.0, "dsr": 0.0, "mar": -0.1}}]}))
    out = tmp_path / "rung2.json"
    path_signal.rung2(str(out), cache_dir=".backtest_cache", n_folds=2,
                      horizons=[6], rung0_path=str(rung0), rung1_path=str(rung1),
                      readers=_readers(500), pool_symbols=["ETHUSDT"])
    doc = json.loads(out.read_text())
    assert doc["config"]["horizons"] == [6]
    assert doc["rung2"] and doc["verdict"]
    assert "beats_rung1" in doc["verdict"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_rung2_cli.py -q`
Expected: FAIL — `AttributeError: module 'path_signal' has no attribute 'rung2'`.

- [ ] **Step 3: Write minimal implementation**

Add the `rung2` function after `ensemble` in `tools/path_signal.py`:

```python
def rung2(out_path: str, cache_dir: str, n_folds: int,
          horizons: list[int], rung0_path: str | None = None,
          rung1_path: str | None = None, open_lockbox: bool = False,
          readers=None, pool_symbols=None) -> None:
    import time

    from moonface.research.pathsig.baseline import POOL_SYMBOLS
    from moonface.research.pathsig.rung2 import run_rung2_to_doc

    rung0_doc = (json.loads(Path(rung0_path).read_text())
                 if rung0_path and Path(rung0_path).exists() else None)
    rung1_doc = (json.loads(Path(rung1_path).read_text())
                 if rung1_path and Path(rung1_path).exists() else None)
    if readers is None:
        from moonface.research.multifamily_loader import default_readers
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)
    doc = run_rung2_to_doc(readers, n_folds=n_folds, horizons=horizons,
                           pool_symbols=pool_symbols or POOL_SYMBOLS,
                           rung0_doc=rung0_doc, rung1_doc=rung1_doc)
    Path(out_path).write_text(json.dumps(doc, indent=2))
    print(f"wrote {out_path}")
    for res, v in zip(doc["rung2"], doc["verdict"]):
        if res["status"] != "ok":
            print(f"  h={res['h']} {res['status']}")
            continue
        fc, ra = res["fixed_cap"], res["risk_adjusted"]
        print(f"  h={res['h']} trades={res['n_trades']} "
              f"total_r={fc['total_r']:+.2f} maxdd_r={fc['max_drawdown_r']:+.2f} "
              f"cap_ok={fc['within_cap']} dsr={ra['dsr']:.3f} "
              f"beats_rung0={v['beats_rung0']} beats_rung1={v['beats_rung1']} "
              f"clears_gate={v['clears_gate']}")
```

Then register the subcommand inside `main`, after the `ensemble` parser block:

```python
    r2 = sub.add_parser("rung2", help="run the rung-2 distributional forest")
    r2.add_argument("--out", default="experiments/path_signal/rung2_forest.json")
    r2.add_argument("--rung0", default="experiments/path_signal/rung0_baseline.json")
    r2.add_argument("--rung1", default="experiments/path_signal/rung1_ensemble.json")
    r2.add_argument("--cache-dir", default=".backtest_cache")
    r2.add_argument("--n-folds", type=int, default=5)
    r2.add_argument("--horizons", type=int, nargs="+", default=[6, 12])
```

And dispatch it, before the final `return 1`:

```python
    if args.cmd == "rung2":
        rung2(args.out, args.cache_dir, args.n_folds, args.horizons,
              rung0_path=args.rung0, rung1_path=args.rung1)
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_rung2_cli.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add tools/path_signal.py tests/test_pathsig_rung2_cli.py
git commit -m "feat(pathsig): rung-2 CLI subcommand"
```

---

## Task 12: Full suite + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the whole pathsig test set**

Run: `python -m pytest tests/ -k pathsig -q`
Expected: PASS — all pathsig tests green (existing rung-0/1 tests plus the new
forest, rung2, and rung2_cli tests).

- [ ] **Step 2: Run ruff**

Run: `ruff check src/moonface/research/pathsig/ tools/path_signal.py tests/test_pathsig_forest.py tests/test_pathsig_rung2.py tests/test_pathsig_rung2_cli.py`
Expected: `All checks passed!` (fix any reported issues, then re-run).

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit -m "chore(pathsig): rung-2 lint cleanup"
```

(Skip this commit if ruff reported nothing.)

---

## Task 13: Real run + run document + results artifact

**Files:**
- Create: `experiments/path_signal/rung2_forest.json` (generated)
- Create: `experiments/path_signal/RUNG2_RUN.md`

This is the real research execution. It produces the verdict that decides the
kill rule (spec §1, pre-registration). **No parameter rescue** if it fails.

- [ ] **Step 1: Run rung-2 on the real cached BTC data**

Run: `python tools/path_signal.py rung2 --n-folds 5 --horizons 6 12`
Expected: writes `experiments/path_signal/rung2_forest.json` and prints one line
per horizon with `total_r`, `dsr`, `beats_rung0`, `beats_rung1`, `clears_gate`.
(This trains 200-tree forests across the nested grid; expect minutes, not
seconds.)

- [ ] **Step 2: Record the verdict in a run document**

Create `experiments/path_signal/RUNG2_RUN.md` mirroring the rung-0/1 run docs:
the config, the per-horizon `total_r` / `max_drawdown_r` / `dsr` under both
frames, the head-to-head vs the rung-0 floor and rung-1, and the explicit
verdict (`beats_rung1 AND beats_rung0 AND clears_gate`?). State the kill-rule
outcome plainly: if rung-2 does not beat rung-1 or does not clear the gate, the
"framework was the limiting factor" thesis is **falsified on existing data** and
the standing recommendation becomes a separate new-data program. Quote the actual
numbers from `rung2_forest.json` — do not assert success without the JSON.

- [ ] **Step 3: Decide on the lockbox (conditional)**

Only if Step 1 shows `beats_rung1 AND beats_rung0 AND clears_gate` for a horizon,
open the sealed tail exactly once. There is no auto-run; add a one-off invocation
(a short `python -c` calling `open_lockbox` on the built samples, or extend the
CLI with `--open-lockbox` following the Task 11 pattern) and record the tail
result in `RUNG2_RUN.md`. If no horizon clears OOS, **do not open the lockbox**;
note that it remains sealed.

- [ ] **Step 4: Commit the artifact and run document**

```bash
git add -f experiments/path_signal/rung2_forest.json experiments/path_signal/RUNG2_RUN.md
git diff --cached --stat
git commit -m "chore(pathsig): rung-2 forest run document and results artifact"
```

(`experiments/` may be partially git-ignored; use `-f` to match how the rung-0/1
artifacts were tracked, and verify `git diff --cached --stat` before committing.)

- [ ] **Step 5: Update auto-memory**

Update the author's private notes (`distributional-path-program.md`, not published)
with the rung-2 outcome (beats/clears booleans per horizon, the kill-rule
result, lockbox status) and refresh its one-line pointer in `MEMORY.md`.

---

## Self-Review Notes

- **Spec coverage:** model §3 → Tasks 1-3; decision + ruin clamp §4 → Tasks 4-5;
  nested CV §5 → Tasks 6-7; lockbox §6 → Task 10; verdict + output §7 → Tasks
  8-9, 13; files §8 → all tasks; deflation trial count (48) → Task 9 config +
  Task 13 run.
- **Determinism / one-touch lockbox:** frozen `SEED`; lockbox is a separate
  function never called by `run_rung2_to_doc` (Tasks 9-10).
- **Attribution invariant:** `decide()` is reused unchanged; only the
  `Distribution` source differs from rungs 0/1 (Task 5).
- **Type consistency:** `PathPrediction(dist, q05, q50, q95)`, `DistForest(*,
  n_trees, max_depth, min_leaf, mtry, seed).fit(X, labels).predict(x)`,
  `ConfigChoice(structure, edge_threshold, trial_srs)` used identically across
  Tasks 3-10. `X_matrix`/`labels_matrix`/`fit_config`/`replay_positions`/
  `select_config`/`replay_forest`/`rung2_verdict`/`run_rung2_to_doc`/
  `open_lockbox` names match between definition and call sites.
- **Frozen feature list untouched:** no task edits `features.py`.
