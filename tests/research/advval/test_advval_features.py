import math
import unittest

from moonface.core.models import Candle
from moonface.research.advval.features import (
    build_dataset,
    funding_features,
    oi_features,
    price_features,
    trailing_z,
)


def make_candles(closes, base_ts=1_640_995_200_000, step=14_400_000):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(base_ts + i * step, c, c * 1.01, c * 0.99, c, 100.0))
    return out


class TrailingZTest(unittest.TestCase):
    def test_none_until_window_full(self):
        vals = [float(i) for i in range(10)]
        z = trailing_z(vals, window=5)
        self.assertEqual(z[:5], [None] * 5)
        self.assertIsNotNone(z[5])

    def test_no_lookahead(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        z_a = trailing_z(vals, window=5)
        vals_b = vals[:6] + [999.0]
        z_b = trailing_z(vals_b, window=5)
        self.assertEqual(z_a[5], z_b[5])

    def test_zero_std_is_none(self):
        z = trailing_z([2.0] * 8, window=5)
        self.assertEqual(z, [None] * 8)

    def test_z_value(self):
        z = trailing_z([0.0, 1.0, 2.0, 3.0, 4.0, 7.0], window=5)
        self.assertAlmostEqual(z[5], 5.0 / (2.5 ** 0.5), places=12)


class PriceFeaturesTest(unittest.TestCase):
    def test_empty_input(self):
        feats = price_features([])
        self.assertEqual(
            feats,
            {
                "log_ret": [],
                "abs_ret_z": [],
                "range_frac": [],
                "close_loc": [],
                "vol_z": [],
                "up_frac_30": [],
            },
        )

    def test_keys_and_lengths(self):
        candles = make_candles([100.0 + i for i in range(120)])
        feats = price_features(candles)
        self.assertEqual(
            sorted(feats),
            ["abs_ret_z", "close_loc", "log_ret", "range_frac", "up_frac_30", "vol_z"],
        )
        for series in feats.values():
            self.assertEqual(len(series), 120)

    def test_close_loc_degenerate_bar(self):
        c = Candle(0, 5.0, 5.0, 5.0, 5.0, 10.0)
        feats = price_features([c, c])
        self.assertEqual(feats["close_loc"][1], 0.5)

    def test_up_frac_monotone_series(self):
        candles = make_candles([100.0 * (1.01 ** i) for i in range(40)])
        feats = price_features(candles)
        self.assertEqual(feats["up_frac_30"][39], 1.0)


class FundingFeaturesTest(unittest.TestCase):
    def test_empty_input(self):
        feats = funding_features([])
        self.assertEqual(
            feats,
            {
                "rate": [],
                "rate_z": [],
                "rate_chg": [],
                "abs_rate_z": [],
                "pos_frac_30": [],
            },
        )

    def test_keys_and_pos_frac(self):
        pts = [(i * 28_800_000, 0.0001) for i in range(40)]
        feats = funding_features(pts)
        self.assertEqual(
            sorted(feats),
            ["abs_rate_z", "pos_frac_30", "rate", "rate_chg", "rate_z"],
        )
        self.assertEqual(feats["pos_frac_30"][39], 1.0)
        self.assertEqual(feats["rate"][7], 0.0001)


class OiFeaturesTest(unittest.TestCase):
    def test_none_propagates(self):
        oi = [None] * 3 + [100.0, 110.0, 121.0]
        feats = oi_features(oi)
        self.assertEqual(
            sorted(feats),
            ["abs_chg_z", "oi_chg", "oi_chg30", "oi_chg_z"],
        )
        self.assertIsNone(feats["oi_chg"][3])
        self.assertAlmostEqual(feats["oi_chg"][4], math.log(1.1), places=12)


class BuildDatasetTest(unittest.TestCase):
    def test_empty_feature_map_returns_empty_dataset(self):
        X, y, kept = build_dataset({}, [10, 20], era_split_ms=0)
        self.assertEqual((X, y, kept), ([], [], []))

    def test_drops_none_rows_and_labels_eras(self):
        feats = {"a": [None, 1.0, 2.0, 3.0], "b": [0.5, 0.5, None, 0.5]}
        ts = [10, 20, 30, 40]
        X, y, kept = build_dataset(feats, ts, era_split_ms=35)
        self.assertEqual(kept, [20, 40])
        self.assertEqual(y, [0, 1])
        self.assertEqual(X, [[1.0, 0.5], [3.0, 0.5]])

    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            build_dataset({"a": [1.0, 2.0], "b": [3.0]}, [10, 20], era_split_ms=15)
