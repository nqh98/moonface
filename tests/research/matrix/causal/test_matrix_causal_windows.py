import unittest

from moonface.research.matrix.causal.windows import walk_windows


class WalkWindowsTest(unittest.TestCase):
    def test_embargo_ordering_and_disjointness(self):
        wins = list(walk_windows(n=300, train_bars=100, test_bars=20,
                                 step_bars=20, gap_bars=24))
        self.assertTrue(wins)
        first = wins[0]
        self.assertEqual((first.train_lo, first.train_hi), (0, 100))
        self.assertEqual((first.test_lo, first.test_hi), (124, 144))
        for w in wins:
            self.assertLessEqual(w.train_hi + 24, w.test_lo)
            self.assertLess(w.test_lo, w.test_hi)
            self.assertLessEqual(w.train_hi, w.test_lo)
            self.assertLessEqual(w.test_hi, 300)

    def test_indices_are_sequential(self):
        wins = list(walk_windows(300, 100, 20, 20, 24))
        self.assertEqual([w.index for w in wins], list(range(len(wins))))


if __name__ == "__main__":
    unittest.main()
