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
