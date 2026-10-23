# tests/test_pathsig_forest.py
# ruff: noqa: E402  (numpy + forest imports must follow pytest.importorskip)
import pytest

# numpy backs only the optional rung-2 distributional-forest path; skip when the
# extra isn't installed (`pip install -e ".[pathsig]"`).
pytest.importorskip("numpy")
import numpy as np

from moonface.research.pathsig.forest import (
    DistForest, PathPrediction, _best_split, _grow_tree, _leaf_rows)
from moonface.research.pathsig.policy import Distribution


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


def test_best_split_picks_higher_gain_feature_across_subset():
    # feature 1: perfect step (4.0 for i<5 else 5.0) aligns exactly with y
    # feature 0: interleaved values so optimal split always mixes 0s with 10s,
    #   yielding strictly lower SSE reduction than feat 1
    X = np.array([[0.0, 4.0], [9.0, 4.0], [1.0, 4.0], [8.0, 4.0], [2.0, 4.0],
                  [7.0, 5.0], [3.0, 5.0], [6.0, 5.0], [4.0, 5.0], [5.0, 5.0]])
    y = np.array([0.0] * 5 + [10.0] * 5)
    rows = np.arange(10)
    split = _best_split(X, y, rows, feat_subset=np.array([0, 1]), min_leaf=1)
    assert split is not None
    _, feat, thr = split
    assert feat == 1                      # perfect-step feature wins
    assert 4.0 < thr < 5.0


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


# --- rung-2: DistForest integration tests ---


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
