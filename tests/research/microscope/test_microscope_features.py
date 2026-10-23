import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.microscope.features import (
    FEATURE_KEYS, atr_frac, build_matrix, dist_from_ma, pct_returns,
    persistence, range_frac, realized_vol, rolling_beta, rolling_z,
    series_change,
)
from tests.helpers_microscope import make_bundle, make_candles, make_pool


class RollingZTest(unittest.TestCase):
    def test_none_until_window_full(self):
        out = rolling_z([float(i) for i in range(10)], window=5)
        self.assertEqual(out[:4], [None] * 4)
        self.assertIsNotNone(out[4])

    def test_constant_series_yields_none(self):
        # std == 0 -> z undefined
        out = rolling_z([1.0] * 20, window=5)
        self.assertTrue(all(v is None for v in out))

    def test_ramp_gives_positive_z_at_end(self):
        out = rolling_z([float(i) for i in range(20)], window=10)
        self.assertGreater(out[-1], 1.0)

    def test_none_input_propagates_and_gap_tolerated(self):
        values = [float(i % 7) for i in range(30)]
        values[20] = None
        out = rolling_z(values, window=10, min_frac=0.8)
        self.assertIsNone(out[20])
        self.assertIsNotNone(out[25])

    def test_too_many_gaps_yield_none(self):
        values = [float(i % 7) for i in range(30)]
        for i in range(12, 18):
            values[i] = None
        out = rolling_z(values, window=10, min_frac=0.9)
        self.assertIsNone(out[19])

    def test_matches_direct_computation(self):
        vals = [float(v) for v in (3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5)]
        out = rolling_z(vals, window=5)
        window = vals[6:11]
        mean = sum(window) / 5
        std = (sum((v - mean) ** 2 for v in window) / 5) ** 0.5
        self.assertAlmostEqual(out[10], (vals[10] - mean) / std, places=9)


def _bar(ts, close, spread=1.0):
    return Candle(timestamp_ms=ts, open=close, high=close + spread,
                  low=close - spread, close=close, volume=100.0)


class ColumnTest(unittest.TestCase):
    def test_pct_returns(self):
        out = pct_returns([100.0, 110.0, 121.0], 1)
        self.assertIsNone(out[0])
        self.assertAlmostEqual(out[1], 0.10)
        self.assertAlmostEqual(out[2], 0.10)

    def test_pct_returns_k_gt_1(self):
        out = pct_returns([100.0, 110.0, 121.0], 2)
        self.assertEqual(out[:2], [None, None])
        self.assertAlmostEqual(out[2], 0.21)

    def test_dist_from_ma(self):
        out = dist_from_ma([1.0, 2.0, 3.0, 4.0], period=2)
        self.assertIsNone(out[0])
        self.assertAlmostEqual(out[1], (2.0 - 1.5) / 1.5)
        self.assertAlmostEqual(out[3], (4.0 - 3.5) / 3.5)

    def test_persistence_all_up_is_one(self):
        closes = [float(i) for i in range(1, 20)]
        out = persistence(closes, bars=4)
        self.assertIsNone(out[3])   # first 1-bar return is None
        self.assertAlmostEqual(out[-1], 1.0)

    def test_persistence_all_down_is_minus_one(self):
        closes = [float(i) for i in range(20, 1, -1)]
        self.assertAlmostEqual(persistence(closes, bars=4)[-1], -1.0)

    def test_realized_vol_constant_returns_zero(self):
        closes = [100.0 * (1.1 ** i) for i in range(25)]
        out = realized_vol(closes, window=5)
        self.assertIsNone(out[4])
        self.assertAlmostEqual(out[-1], 0.0, places=9)

    def test_atr_frac_constant_spread(self):
        candles = [_bar(i, 100.0, spread=1.0) for i in range(20)]
        out = atr_frac(candles, period=14)
        self.assertIsNone(out[12])
        self.assertAlmostEqual(out[-1], 2.0 / 100.0)  # TR = high-low = 2

    def test_range_frac(self):
        candles = [_bar(0, 200.0, spread=2.0)]
        self.assertAlmostEqual(range_frac(candles)[0], 4.0 / 200.0)

    def test_series_change(self):
        out = series_change([100.0, None, 110.0, 121.0], k=2)
        self.assertEqual(out[:2], [None, None])
        self.assertAlmostEqual(out[2], 0.10)
        self.assertIsNone(out[3])   # base is None

    def test_series_change_none_series(self):
        self.assertIsNone(series_change(None, k=2))


class RollingBetaTest(unittest.TestCase):
    def test_beta_of_identical_series_is_one(self):
        rng_vals = [((i * 37) % 11) - 5.0 for i in range(120)]
        x: list[float | None] = list(rng_vals)
        out = rolling_beta(x, x, window=90)
        self.assertIsNone(out[88])
        self.assertAlmostEqual(out[100], 1.0, places=9)

    def test_beta_scales(self):
        y: list[float | None] = [((i * 37) % 11) - 5.0 for i in range(120)]
        x: list[float | None] = [2.0 * v for v in y]
        self.assertAlmostEqual(rolling_beta(x, y, window=90)[-1], 2.0,
                               places=9)

    def test_too_many_gaps_is_none(self):
        y: list[float | None] = [((i * 37) % 11) - 5.0 for i in range(120)]
        x = list(y)
        for i in range(95, 115):
            x[i] = None
        self.assertIsNone(rolling_beta(x, y, window=90)[115])


class BuildMatrixTest(unittest.TestCase):
    def test_shapes_and_keys(self):
        pool = make_pool(n=320, n_assets=10, seed=3)
        m = build_matrix(pool)
        self.assertEqual(m.symbols, sorted(pool))
        self.assertEqual(len(m.timestamps), 320)
        for sym in m.symbols:
            self.assertEqual(len(m.rows[sym]), 320)
            self.assertEqual(set(m.rows[sym][0]), set(FEATURE_KEYS))
        self.assertEqual(len(m.mkt_ret_z), 320)
        self.assertEqual(len(m.breadth_z), 320)

    def test_recent_shock_shows_in_own_z(self):
        # flat first, strong drift in the last 60 bars -> ret_6_z positive
        pool = make_pool(n=340, n_assets=10, seed=5)
        flat = make_candles(280, seed=42, drift=0.0)
        hot = make_candles(61, seed=43, drift=0.02,
                           start=flat[-1].close)
        shifted = [Candle(timestamp_ms=flat[-1].timestamp_ms
                          + (i + 1) * 14_400_000, open=c.open, high=c.high,
                          low=c.low, close=c.close, volume=c.volume)
                   for i, c in enumerate(hot[1:])]
        candles = flat + shifted
        pool["HOTUSDT"] = DataBundle(candles=candles,
                                     funding=[0.0001] * 340,
                                     feature=[1e6] * 340)
        m = build_matrix(pool)
        self.assertGreater(m.rows["HOTUSDT"][-1]["ret_6_z"], 0.5)

    def test_outperformer_has_high_rs_xz(self):
        pool = make_pool(n=320, n_assets=10, seed=7)
        pool["MOONUSDT"] = make_bundle(320, seed=77, drift=0.01)
        m = build_matrix(pool)
        self.assertGreater(m.rows["MOONUSDT"][-1]["rs_xz"], 1.0)

    def test_btc_beta_of_btc_is_one(self):
        pool = make_pool(n=320, n_assets=10, seed=9)
        m = build_matrix(pool)
        self.assertAlmostEqual(m.rows["BTCUSDT"][-1]["beta_btc"], 1.0,
                               places=6)

    def test_missing_funding_leaves_other_features_intact(self):
        pool = make_pool(n=320, n_assets=10, seed=11)
        b = pool["A00USDT"]
        pool["A00USDT"] = DataBundle(candles=b.candles, funding=None,
                                     feature=b.feature)
        m = build_matrix(pool)
        row = m.rows["A00USDT"][-1]
        self.assertIsNone(row["funding_z"])
        self.assertIsNotNone(row["ret_1_z"])

    def test_short_history_asset_is_none_early(self):
        pool = make_pool(n=320, n_assets=10, seed=13)
        late = make_bundle(320, seed=99)
        pool["LATEUSDT"] = DataBundle(candles=late.candles[200:],
                                      funding=late.funding[200:],
                                      feature=late.feature[200:])
        m = build_matrix(pool)
        self.assertEqual(len(m.rows["LATEUSDT"]), 320)
        self.assertTrue(all(v is None
                            for v in m.rows["LATEUSDT"][100].values()))


if __name__ == "__main__":
    unittest.main()
