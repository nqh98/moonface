import unittest

from moonface.research.microscope.factors import (
    FACTOR_CAP, FACTOR_NAMES, state_row, state_vectors,
)
from moonface.research.microscope.features import FEATURE_KEYS, build_matrix
from tests.helpers_microscope import make_pool


def _features(**overrides):
    base = dict.fromkeys(FEATURE_KEYS)
    base.update(overrides)
    return base


class StateRowTest(unittest.TestCase):
    def test_factor_names(self):
        self.assertEqual(FACTOR_NAMES, ("trend", "vol", "crowding", "flow",
                                        "relative_strength"))

    def test_group_means(self):
        row = state_row(_features(ret_1_z=1.0, ret_6_z=2.0, ret_42_z=3.0,
                                  dist_ma_z=2.0, persist_z=2.0,
                                  rvol_z=-1.0, atr_z=-2.0, range_z=-3.0,
                                  funding_z=2.0, oi_chg_z=0.0,
                                  volume_z=1.5, rs_xz=-0.5))
        self.assertAlmostEqual(row["trend"], 2.0)
        self.assertAlmostEqual(row["vol"], -2.0)
        self.assertAlmostEqual(row["crowding"], 1.0)
        self.assertAlmostEqual(row["flow"], 1.5)
        self.assertAlmostEqual(row["relative_strength"], -0.5)

    def test_partial_group_uses_available(self):
        row = state_row(_features(funding_z=2.0))   # oi_chg_z missing
        self.assertAlmostEqual(row["crowding"], 2.0)

    def test_empty_group_is_none(self):
        row = state_row(_features(ret_1_z=1.0))
        self.assertIsNone(row["flow"])

    def test_cap(self):
        row = state_row(_features(volume_z=9.0))
        self.assertAlmostEqual(row["flow"], FACTOR_CAP)
        row = state_row(_features(volume_z=-9.0))
        self.assertAlmostEqual(row["flow"], -FACTOR_CAP)


class StateVectorsTest(unittest.TestCase):
    def test_shapes(self):
        m = build_matrix(make_pool(n=320, n_assets=10, seed=3))
        states = state_vectors(m)
        self.assertEqual(sorted(states), m.symbols)
        for sym in m.symbols:
            self.assertEqual(len(states[sym]), len(m.timestamps))
            self.assertEqual(set(states[sym][-1]), set(FACTOR_NAMES))


if __name__ == "__main__":
    unittest.main()
