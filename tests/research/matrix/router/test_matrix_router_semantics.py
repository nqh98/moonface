import unittest

from moonface.research.matrix.router.semantics import (
    ENTROPY_FREEZE,
    MODE_FREEZE,
    MODE_QUARANTINE,
    MODE_TREND,
    apply_entropy_override,
    rank_modes,
)


class RankModesTest(unittest.TestCase):
    def test_three_states_rank_to_modes(self):
        m = rank_modes({0: -0.5, 1: 1.0, 2: 0.2}, k=3)
        self.assertEqual(m, {1: MODE_TREND, 2: MODE_QUARANTINE, 0: MODE_FREEZE})

    def test_missing_score_defaults_to_freeze(self):
        m = rank_modes({0: 1.0, 1: None, 2: -1.0}, k=3)
        self.assertEqual(m[1], MODE_FREEZE)
        self.assertEqual(m[0], MODE_TREND)
        self.assertEqual(m[2], MODE_FREEZE)

    def test_single_defined_state_is_trend(self):
        m = rank_modes({0: None, 1: 0.3, 2: None}, k=3)
        self.assertEqual(m[1], MODE_TREND)
        self.assertEqual(m[0], MODE_FREEZE)
        self.assertEqual(m[2], MODE_FREEZE)

    def test_ties_break_by_state_index(self):
        m = rank_modes({0: 0.5, 1: 0.5, 2: 0.5}, k=3)
        self.assertEqual(m, {0: MODE_TREND, 1: MODE_QUARANTINE, 2: MODE_FREEZE})


class EntropyOverrideTest(unittest.TestCase):
    def test_high_entropy_forces_freeze(self):
        self.assertEqual(
            apply_entropy_override(MODE_TREND, ENTROPY_FREEZE + 0.1), MODE_FREEZE
        )

    def test_low_entropy_keeps_mode(self):
        self.assertEqual(apply_entropy_override(MODE_QUARANTINE, 0.0), MODE_QUARANTINE)


if __name__ == "__main__":
    unittest.main()
