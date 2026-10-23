import unittest

from moonface.kernel.fwd_null import shuffle_funding_segments


class NullShuffleTest(unittest.TestCase):
    SERIES = [None, 0.1, 0.2, 0.3, None, None, 0.4, 0.5, 0.6, 0.7, None]

    def test_gaps_preserved_exactly(self):
        out = shuffle_funding_segments(self.SERIES, seed=0)
        self.assertEqual([i for i, v in enumerate(out) if v is None],
                         [i for i, v in enumerate(self.SERIES) if v is None])

    def test_values_preserved_per_segment(self):
        out = shuffle_funding_segments(self.SERIES, seed=0)
        self.assertEqual(sorted(out[1:4]), [0.1, 0.2, 0.3])
        self.assertEqual(sorted(out[6:10]), [0.4, 0.5, 0.6, 0.7])

    def test_deterministic_per_seed(self):
        self.assertEqual(shuffle_funding_segments(self.SERIES, seed=5),
                         shuffle_funding_segments(self.SERIES, seed=5))

    def test_seeds_differ(self):
        series = [float(i) for i in range(200)]
        self.assertNotEqual(shuffle_funding_segments(series, seed=0),
                            shuffle_funding_segments(series, seed=1))

    def test_input_not_mutated(self):
        original = list(self.SERIES)
        shuffle_funding_segments(self.SERIES, seed=0)
        self.assertEqual(self.SERIES, original)
