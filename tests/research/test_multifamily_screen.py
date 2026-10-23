import unittest

from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.drift_screen import (score_family_on_asset,
                                             screen_family, horizon_curve)
from moonface.research.entries import generate_entries, known_families

H4 = 4 * 3_600_000


def _c(i, close=100.0):
    return Candle(i * H4, close, close + 1, close - 1, close, 1000.0)


class TestEntriesObImbalance(unittest.TestCase):
    def test_ob_imbalance_follow_is_known(self):
        self.assertIn("ob_imbalance_follow", known_families())

    def test_routes_to_bundle_bookdepth(self):
        n = 40
        candles = [_c(i) for i in range(n)]
        bookdepth = [0.0] * n
        bookdepth[30] = 5.0
        bundle = DataBundle(candles=candles, bookdepth=bookdepth)
        out = generate_entries("ob_imbalance_follow",
                               {"window": 20, "z_thr": 1.5}, bundle)
        self.assertIn((30, "LONG"), out)

    def test_missing_bookdepth_raises(self):
        bundle = DataBundle(candles=[_c(i) for i in range(5)])
        with self.assertRaises(ValueError):
            generate_entries("ob_imbalance_follow",
                             {"window": 2, "z_thr": 1.5}, bundle)


class TestScreenFamily(unittest.TestCase):
    def _bid_drift_bundle(self):
        # 30 flat bars, then 20 up bars; positive imbalance spikes precede ups
        n = 50
        candles = [_c(i, 100.0) for i in range(30)] + [
            Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                   100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(20)]
        book = [0.0] * n
        for i in range(28, 48):           # strong bid imbalance before each up
            book[i] = 4.0
        return DataBundle(candles=candles, bookdepth=book)

    def test_score_family_on_asset_produces_stats(self):
        bundle = self._bid_drift_bundle()
        stats = score_family_on_asset("ob_imbalance_follow",
                                      {"window": 20, "z_thr": 1.0}, bundle,
                                      h=3, atr_period=14)
        self.assertGreaterEqual(stats["n"], 1)
        self.assertIn("mean_mfe_r", stats)
        self.assertIn("sign_rate", stats)

    def test_screen_family_renders_verdict_and_identity(self):
        pool = {f"A{j}": self._bid_drift_bundle() for j in range(9)}
        result = screen_family("ob_imbalance_follow",
                               {"window": 20, "z_thr": 1.0}, pool,
                               h=3, atr_period=14, floor=0.1,
                               min_events=1, min_assets=8)
        self.assertEqual(result["signal"], "ob_imbalance_follow")
        self.assertEqual(result["params"], {"window": 20, "z_thr": 1.0})
        self.assertEqual(result["h"], 3)
        # deterministic strong unidirectional up-drift (sign_rate=1.0,
        # ratio >> floor 0.1) -> the gate must fire mechanism_exists, not just
        # any tripartite member (catches a pooled-gate wiring regression).
        self.assertEqual(result["verdict"]["verdict"], "mechanism_exists")

    def test_asset_failing_family_data_is_dropped(self):
        pool = {f"A{j}": self._bid_drift_bundle() for j in range(8)}
        pool["NOBOOK"] = DataBundle(candles=[_c(i) for i in range(50)])
        result = screen_family("ob_imbalance_follow",
                               {"window": 20, "z_thr": 1.0}, pool,
                               h=3, atr_period=14, floor=0.1,
                               min_events=1, min_assets=8)
        self.assertNotIn("NOBOOK", [a["sym"] for a in result["assets"]])
        # exactly the no-data asset was dropped; the 8 good ones survived
        # (guards against a bug that silently drops everything).
        self.assertEqual(len(result["assets"]), 8)


class TestHorizonCurve(unittest.TestCase):
    def _pool(self, n=9):
        return {f"A{j}": TestScreenFamily()._bid_drift_bundle()
                for j in range(n)}

    def test_curve_has_one_row_per_horizon(self):
        curve = horizon_curve("ob_imbalance_follow",
                              {"window": 20, "z_thr": 1.0}, self._pool(),
                              horizons=[3, 6, 12], atr_period=14,
                              min_events=1, min_assets=8)
        self.assertEqual([row["h"] for row in curve], [3, 6, 12])
        for row in curve:
            self.assertIn("pooled_ret_r", row)
            self.assertIn("pooled_sign_rate", row)
            self.assertIn("pooled_abs_mae_r", row)
            self.assertIn("pooled_mfe_r", row)
            self.assertIn("stouffer_z", row)
            self.assertIn("m_assets", row)
            self.assertIn("pooled", row)

    def test_populated_row_carrys_positive_drift(self):
        # strong unidirectional up-drift: every surviving asset drifts up, so
        # the populated row must read pooled==True with positive forward drift
        # and a +1 sign rate (locks the pooling wiring, not just key names).
        curve = horizon_curve("ob_imbalance_follow",
                              {"window": 20, "z_thr": 1.0}, self._pool(),
                              horizons=[3], atr_period=14,
                              min_events=1, min_assets=8)
        row = curve[0]
        self.assertTrue(row["pooled"])
        self.assertGreater(row["pooled_ret_r"], 0.0)
        self.assertGreater(row["stouffer_z"], 0.0)
        self.assertAlmostEqual(row["pooled_sign_rate"], 1.0)

    def test_sparse_row_below_min_assets_is_marked_unpooled(self):
        # too few assets to pool: the row is emitted (term structure visible)
        # but marked pooled=False with null pooled fields so a consumer cannot
        # misread it as "no drift".
        curve = horizon_curve("ob_imbalance_follow",
                              {"window": 20, "z_thr": 1.0}, self._pool(n=9),
                              horizons=[3], atr_period=14,
                              min_events=1, min_assets=20)
        self.assertEqual(len(curve), 1)
        row = curve[0]
        self.assertFalse(row["pooled"])
        self.assertEqual(row["m_assets"], 9)
        self.assertIsNone(row["pooled_ret_r"])
        self.assertIsNone(row["stouffer_z"])
