import unittest

from moonface.research.advval.gbt import (auc, block_folds, cv_auc, fit_gbt,
                                          predict)


def synth(n_per_era, shift, seed=7):
    """Two-era dataset: feature 0 shifts by `shift` in era 1; feature 1 noise."""
    import random
    rng = random.Random(seed)
    X, y = [], []
    for era in (0, 1):
        for _ in range(n_per_era):
            X.append([rng.gauss(shift * era, 1.0), rng.gauss(0.0, 1.0)])
            y.append(era)
    return X, y


class AucTest(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]), 1.0)

    def test_reversed(self):
        self.assertEqual(auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]), 0.0)

    def test_ties_give_half(self):
        self.assertEqual(auc([0.5, 0.5, 0.5, 0.5], [0, 0, 1, 1]), 0.5)

    def test_non_binary_labels_rejected(self):
        with self.assertRaises(ValueError):
            auc([0.1, 0.2, 0.3], [0, 1, 2])


class BlockFoldsTest(unittest.TestCase):
    def test_partition_and_embargo(self):
        folds = block_folds(100, n_folds=5, embargo=3)
        self.assertEqual(len(folds), 5)
        all_test = sorted(i for _, test in folds for i in test)
        self.assertEqual(all_test, list(range(100)))
        train1, test1 = folds[1]
        self.assertEqual(test1, list(range(20, 40)))
        for banned in (17, 18, 19, 40, 41, 42):
            self.assertNotIn(banned, train1)
        self.assertIn(16, train1)
        self.assertIn(43, train1)

    def test_negative_embargo_rejected(self):
        with self.assertRaises(ValueError):
            block_folds(10, n_folds=5, embargo=-1)


class GbtTest(unittest.TestCase):
    def test_fit_rejects_single_class(self):
        X = [[1.0, 2.0]] * 20
        y = [1] * 20
        with self.assertRaises(ValueError):
            fit_gbt(X, y, rounds=10, lr=0.1, min_leaf=5)

    def test_separable_shift_high_auc(self):
        X, y = synth(200, shift=2.0)
        model = fit_gbt(X, y, rounds=30, lr=0.1, min_leaf=10)
        scores = predict(model, X)
        self.assertGreater(auc(scores, y), 0.9)

    def test_no_shift_cv_auc_near_half(self):
        X, y = synth(200, shift=0.0)
        val = cv_auc(X, y, n_folds=5, embargo=5, rounds=30, lr=0.1, min_leaf=10)
        self.assertLess(abs(val - 0.5), 0.12)

    def test_shift_cv_auc_high(self):
        X, y = synth(200, shift=2.0)
        val = cv_auc(X, y, n_folds=5, embargo=5, rounds=30, lr=0.1, min_leaf=10)
        self.assertGreater(val, 0.85)

    def test_deterministic(self):
        X, y = synth(100, shift=1.0)
        a = cv_auc(X, y, n_folds=5, embargo=5, rounds=20, lr=0.1, min_leaf=10)
        b = cv_auc(X, y, n_folds=5, embargo=5, rounds=20, lr=0.1, min_leaf=10)
        self.assertEqual(a, b)

    def test_constant_features_score_half(self):
        X = [[1.0, 2.0]] * 50 + [[1.0, 2.0]] * 50
        y = [0] * 50 + [1] * 50
        val = cv_auc(X, y, n_folds=5, embargo=2, rounds=10, lr=0.1, min_leaf=5)
        self.assertEqual(val, 0.5)

    def test_single_class_cv_rejected(self):
        X = [[1.0, 2.0]] * 20
        y = [0] * 20
        with self.assertRaises(ValueError):
            cv_auc(X, y, n_folds=5, embargo=2, rounds=10, lr=0.1, min_leaf=5)

    def test_too_small_cv_rejected(self):
        X = [[1.0, 2.0], [2.0, 3.0]]
        y = [0, 1]
        with self.assertRaises(ValueError):
            cv_auc(X, y, n_folds=5, embargo=2, rounds=10, lr=0.1, min_leaf=5)

    def test_asymmetric_eras_with_wide_embargo(self):
        X = [[0.0, 0.0]] * 8 + [[2.0, 0.0]] * 30
        y = [0] * 8 + [1] * 30
        val = cv_auc(X, y, n_folds=5, embargo=3, rounds=10, lr=0.1, min_leaf=2)
        self.assertEqual(val, 1.0)
