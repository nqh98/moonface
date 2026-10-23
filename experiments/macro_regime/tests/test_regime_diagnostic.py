import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import regime_diagnostic as rd  # noqa: E402


def _fake_frame(n=60, n_components=3, seed=0):
    """A minimal labeled-frame stand-in: geometric BTC path + cyclic regimes + entropy."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    daily = rng.normal(0.001, 0.02, n)
    close = 10000 * np.exp(np.cumsum(daily))
    return pd.DataFrame(
        {
            "BTC_close": close,
            "BTC_logret": daily,
            "regime_argmax": np.arange(n) % n_components,
            "entropy_norm": rng.uniform(0, 1, n),
        },
        index=idx,
    )


class TestForwardOutcomes(unittest.TestCase):
    def test_forward_return_matches_definition(self):
        frame = _fake_frame(n=40)
        out = rd.add_forward_outcomes(frame, horizons=(1, 5))
        logc = np.log(frame["BTC_close"])
        expected_1 = (logc.shift(-1) - logc)
        # compare only where a full forward window exists
        valid = out["fwd_logret_1"].notna()
        np.testing.assert_allclose(
            out.loc[valid, "fwd_logret_1"].values, expected_1[valid].values, atol=1e-12
        )
        # last row has no t+1 -> NaN
        self.assertTrue(np.isnan(out["fwd_logret_1"].iloc[-1]))

    def test_forward_columns_present(self):
        out = rd.add_forward_outcomes(_fake_frame(), horizons=(1, 5, 20))
        for h in (1, 5, 20):
            self.assertIn(f"fwd_logret_{h}", out.columns)
            self.assertIn(f"fwd_vol_{h}", out.columns)


class TestTables(unittest.TestCase):
    def test_outcome_table_one_row_per_state(self):
        table = rd.regime_outcome_table(_fake_frame(n_components=3), 3, horizons=(1, 5))
        self.assertEqual(len(table), 3)
        self.assertListEqual(list(table["state"]), [0, 1, 2])
        # occupancies sum to ~1
        self.assertAlmostEqual(float(table["occupancy"].sum()), 1.0, places=6)

    def test_separation_summary_shape(self):
        table = rd.regime_outcome_table(_fake_frame(), 3, horizons=(1, 5, 20))
        sep = rd.separation_summary(table, horizons=(1, 5, 20))
        self.assertListEqual(list(sep["horizon"]), [1, 5, 20])
        self.assertTrue((sep["return_spread"] >= 0).all())

    def test_entropy_split_two_buckets(self):
        split = rd.entropy_split_table(_fake_frame(n=80), horizons=(1, 5))
        self.assertListEqual(list(split["bucket"]), ["low_entropy", "high_entropy"])


def _era_frame(n=1200, n_components=3, seed=1):
    """Labeled-frame stand-in spanning 2017->2024 so all three eras are populated."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2017-01-01", periods=n)
    daily = rng.normal(0.0005, 0.02, n)
    close = 10000 * np.exp(np.cumsum(daily))
    return pd.DataFrame(
        {
            "BTC_close": close,
            "BTC_logret": daily,
            "regime_argmax": np.arange(n) % n_components,
            "entropy_norm": rng.uniform(0, 1, n),
        },
        index=idx,
    )


class TestEraStability(unittest.TestCase):
    def test_era_split_is_disjoint_and_exhaustive(self):
        frame = _era_frame()
        eras = rd.era_split(frame)
        self.assertEqual(len(eras), 3)
        self.assertEqual(sum(len(v) for v in eras.values()), len(frame))
        # boundaries respected
        keys = list(eras.keys())
        self.assertTrue((eras[keys[1]].index >= pd.Timestamp("2020-01-01")).all())
        self.assertTrue((eras[keys[1]].index < pd.Timestamp("2023-01-01")).all())

    def test_report_has_row_per_era_with_flags(self):
        report = rd.era_stability_report(_era_frame(), 3, horizon=20)
        self.assertEqual(len(report), 3)
        for col in ("state1_is_flattest", "entropy_monotone", "pattern_holds"):
            self.assertIn(col, report.columns)

    def test_verdict_fragile_when_any_era_fails(self):
        report = pd.DataFrame([
            {"pattern_holds": True},
            {"pattern_holds": False},
            {"pattern_holds": True},
        ])
        self.assertIn("FRAGILE", rd.era_verdict(report))

    def test_verdict_stable_when_all_hold(self):
        report = pd.DataFrame([{"pattern_holds": True}, {"pattern_holds": True}])
        self.assertIn("STABLE", rd.era_verdict(report))

    def test_entropy_monotone_flag_tracks_construction(self):
        # build a frame where low-entropy days systematically precede higher forward returns.
        # Use persistent 100-day blocks so the signal survives the forward window (not alternating,
        # which would average out): confident blocks trend up, uncertain blocks trend down.
        rng = np.random.default_rng(3)
        block = 100
        n = 4 * block
        idx = pd.bdate_range("2020-01-01", periods=n)
        confident = (np.arange(n) // block) % 2 == 0     # blocks 0,2 confident; 1,3 uncertain
        ent = np.where(confident, 0.1, 0.9)
        daily = np.where(confident, 0.01, -0.01) + rng.normal(0, 1e-4, n)
        close = 10000 * np.exp(np.cumsum(daily))
        frame = pd.DataFrame(
            {"BTC_close": close, "BTC_logret": daily,
             "regime_argmax": np.arange(n) % 3, "entropy_norm": ent},
            index=idx,
        )
        report = rd.era_stability_report(frame, 3, horizon=5,
                                         bounds=("2021-01-01", "2099-01-01"))
        sized = report[report["pattern_holds"].notna()]
        self.assertTrue(bool(sized["entropy_monotone"].iloc[0]))


if __name__ == "__main__":
    unittest.main()
