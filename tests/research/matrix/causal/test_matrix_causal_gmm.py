import random
import unittest

from moonface.research.matrix.causal.gmm import CausalGMM


def _two_blobs(seed):
    rng = random.Random(seed)
    pts = []
    for _ in range(60):
        pts.append([rng.gauss(0.0, 0.3), rng.gauss(0.0, 0.3)])
    for _ in range(60):
        pts.append([rng.gauss(10.0, 0.3), rng.gauss(10.0, 0.3)])
    return pts


class CausalGMMTest(unittest.TestCase):
    def test_proba_rows_sum_to_one(self):
        X = _two_blobs(1)
        gmm = CausalGMM(k=2, seed=7).fit(X)
        for row in gmm.predict_proba(X):
            self.assertEqual(len(row), 2)
            self.assertAlmostEqual(sum(row), 1.0, places=9)

    def test_deterministic_same_seed(self):
        X = _two_blobs(1)
        a = CausalGMM(k=2, seed=7).fit(X).predict_proba(X)
        b = CausalGMM(k=2, seed=7).fit(X).predict_proba(X)
        self.assertEqual(a, b)

    def test_recovers_two_separated_clusters(self):
        X = _two_blobs(1)
        gmm = CausalGMM(k=2, seed=7).fit(X)
        top = [max(range(2), key=lambda c: p[c]) for p in gmm.predict_proba(X)]
        self.assertEqual(len(set(top[:60])), 1)
        self.assertEqual(len(set(top[60:])), 1)
        self.assertNotEqual(top[0], top[60])


if __name__ == "__main__":
    unittest.main()
