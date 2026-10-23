# src/moonface/research/pathsig/forest.py
"""From-scratch distributional random forest for the rung-2 path model.

A CART regression tree is grown to reduce the variance of ret_r; each leaf
retains the row indices of its members so the empirical (ret_r, mae_r, mfe_r)
distribution can be pooled across bagged trees at predict time. Pure numpy,
seeded for reproducibility (the one-touch lockbox depends on determinism).
Design frozen in docs/research-log/specs/2026-06-17-pathsig-rung2-distributional-forest-design.md."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass

from moonface.research.pathsig.policy import Distribution


def _best_split(X: np.ndarray, y: np.ndarray, rows: np.ndarray,
                feat_subset: np.ndarray, min_leaf: int) -> tuple[float, int, float] | None:
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
