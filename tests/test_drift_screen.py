# tests/test_drift_screen.py
import unittest

from moonface.core.models import Candle
from moonface.research.drift_screen import (asset_path_stats, drift_verdict,
                                            event_outcome, screen_signal,
                                            score_signal_on_asset)

H4 = 4 * 3_600_000


def _candle(i, o, h, low, c):
    return Candle(i * H4, o, h, low, c, 1000.0)


class TestEventOutcome(unittest.TestCase):
    def test_long_drift_no_adverse_excursion(self):
        # flat-then-up, never trades below entry close (100) -> mae_r == 0
        candles = [_candle(0, 100, 100, 100, 100)] + [
            _candle(i, 100 + i, 100 + i, 100 + i, 100 + i) for i in range(1, 6)
        ]
        # atr over [0..i] is ~1.0 after warmup; use atr_period=2, h=3
        out = event_outcome(candles, i=2, side="LONG", h=3, atr_period=2)
        self.assertIsNotNone(out)
        ret_r, mae_r, mfe_r = out
        self.assertGreater(ret_r, 0.0)
        self.assertEqual(mae_r, 0.0)
        self.assertGreaterEqual(mfe_r, ret_r)  # favorable excursion >= endpoint

    def test_long_drift_with_midhorizon_dip(self):
        # entry close 100, dips to low 90 mid-horizon, recovers to 106
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry bar i=2, close 100
            _candle(3, 100, 102, 90, 95),    # adverse: low 90
            _candle(4, 95, 107, 95, 106),
            _candle(5, 106, 107, 105, 106),
        ]
        out = event_outcome(candles, i=2, side="LONG", h=2, atr_period=2)
        self.assertIsNotNone(out)
        ret_r, mae_r, mfe_r = out
        self.assertGreater(ret_r, 0.0)       # closed up at i+2
        self.assertLess(mae_r, 0.0)          # lived through a drawdown
        self.assertGreaterEqual(mfe_r, 0.0)
        # mae_r is (90 - 100)/atr_unit; ret_r is (106 - 100)/atr_unit
        self.assertAlmostEqual(ret_r / -mae_r, 6.0 / 10.0, places=4)

    def test_short_uses_high_for_adverse(self):
        # SHORT entry close 100; price spikes high 110 against, closes 94
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry i=2
            _candle(3, 100, 110, 100, 96),   # adverse high 110
            _candle(4, 96, 97, 93, 94),
        ]
        out = event_outcome(candles, i=2, side="SHORT", h=2, atr_period=2)
        ret_r, mae_r, mfe_r = out
        self.assertGreater(ret_r, 0.0)       # short profited (price fell)
        self.assertLess(mae_r, 0.0)
        self.assertGreaterEqual(mfe_r, 0.0)
        # adverse = (close - high)/unit = (100 - 110)/unit ; ret = (100-94)/unit
        self.assertAlmostEqual(ret_r / -mae_r, 6.0 / 10.0, places=4)

    def test_mfe_captures_best_favorable_for_long(self):
        # LONG entry close 100, spikes high 130 mid-horizon, closes 100 (flat)
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry i=2
            _candle(3, 100, 130, 100, 100),  # favorable high 130
            _candle(4, 100, 101, 99, 100),
        ]
        ret_r, mae_r, mfe_r = event_outcome(candles, i=2, side="LONG", h=2,
                                            atr_period=2)
        self.assertGreater(mfe_r, 0.0)          # saw +30 at the high
        self.assertAlmostEqual(ret_r, 0.0)      # closed flat

    def test_mfe_uses_low_for_short(self):
        # SHORT entry close 100, dips low 70 mid-horizon, closes 100 (flat)
        candles = [
            _candle(0, 100, 101, 99, 100),
            _candle(1, 100, 101, 99, 100),
            _candle(2, 100, 101, 99, 100),   # entry i=2
            _candle(3, 100, 100, 70, 100),   # favorable low 70 for SHORT
            _candle(4, 100, 101, 99, 100),
        ]
        ret_r, mae_r, mfe_r = event_outcome(candles, i=2, side="SHORT", h=2,
                                            atr_period=2)
        self.assertGreater(mfe_r, 0.0)          # SHORT favorable uses bar.low
        self.assertAlmostEqual(ret_r, 0.0)      # closed flat

    def test_untradeable_entry_returns_none(self):
        candles = [_candle(i, 100, 100, 100, 100) for i in range(4)]
        # zero ATR -> _risk None -> outcome None
        self.assertIsNone(event_outcome(candles, i=1, side="LONG", h=2, atr_period=2))

    def test_insufficient_future_bars_returns_none(self):
        candles = [_candle(i, 100, 101, 99, 100 + i) for i in range(4)]
        # i + h beyond series
        self.assertIsNone(event_outcome(candles, i=3, side="LONG", h=5, atr_period=2))


class TestAssetPathStats(unittest.TestCase):
    def test_aggregates_ret_mae_mfe_and_sign(self):
        outcomes = [(2.0, -1.0, 3.0), (4.0, -3.0, 5.0), (-3.0, -2.0, 1.0)]
        s = asset_path_stats(outcomes)
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["mean_ret_r"], 1.0)
        self.assertAlmostEqual(s["mean_abs_mae_r"], 2.0)
        self.assertAlmostEqual(s["mean_mfe_r"], 3.0)
        self.assertAlmostEqual(s["sign_rate"], 2.0 / 3.0)
        self.assertNotEqual(s["t"], 0.0)

    def test_empty_is_zeroed(self):
        s = asset_path_stats([])
        self.assertEqual(s["n"], 0)
        self.assertEqual(s["mean_ret_r"], 0.0)
        self.assertEqual(s["mean_abs_mae_r"], 0.0)
        self.assertEqual(s["mean_mfe_r"], 0.0)
        self.assertEqual(s["sign_rate"], 0.0)
        self.assertEqual(s["t"], 0.0)

    def test_t_matches_oibuild_asset_stats(self):
        from moonface.features.oi_features import asset_stats
        outcomes = [(2.0, -1.0, 3.0), (4.0, -3.0, 5.0),
                    (3.0, -2.0, 4.0), (1.0, -0.5, 2.0)]
        rets = [r for r, _, _ in outcomes]
        self.assertAlmostEqual(asset_path_stats(outcomes)["t"],
                               asset_stats(rets)["t"], places=10)


def _stats(mean_ret, mean_abs_mae, t, n=30):
    return {"n": n, "mean_ret_r": mean_ret, "mean_abs_mae_r": mean_abs_mae, "t": t}


class TestDriftVerdict(unittest.TestCase):
    def test_too_few_assets_inconclusive(self):
        v = drift_verdict([_stats(1.0, 0.5, 3.0)] * 3, floor=0.5, min_assets=8)
        self.assertEqual(v["verdict"], "inconclusive")
        self.assertIn("insufficient", v["reason"])

    def test_drift_and_path_pass_is_exists(self):
        stats = [_stats(1.0, 0.5, 3.0) for _ in range(12)]
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_exists")
        self.assertGreaterEqual(v["ratio"], 1.0)

    def test_nonpositive_pooled_ret_is_does_not_exist(self):
        stats = [_stats(-0.1, 0.5, -0.5) for _ in range(12)]
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_does_not_exist")

    def test_drift_passes_but_ratio_below_floor_is_inconclusive(self):
        stats = [_stats(1.0, 5.0, 3.0) for _ in range(12)]
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertEqual(v["verdict"], "inconclusive")
        self.assertLess(v["ratio"], 1.0)
        self.assertIn("path", v["reason"])

    def test_breadth_fails_is_does_not_exist(self):
        stats = ([_stats(1.0, 0.5, 0.2) for _ in range(6)]
                 + [_stats(-0.9, 0.5, -0.2) for _ in range(6)])
        v = drift_verdict(stats, floor=1.0, min_assets=8)
        self.assertIn(v["verdict"], ("mechanism_does_not_exist", "inconclusive"))


class TestScoreSignalOnAsset(unittest.TestCase):
    def test_donchian_long_breakout_drifts_up(self):
        from moonface.research.edge.signals import donchian_break
        # 30 flat bars then a clean uptrend -> donchian_break(n=10) fires LONG
        flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(30)]
        up = [Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                     100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(20)]
        candles = flat + up
        stats = score_signal_on_asset(candles, donchian_break, {"n": 10},
                                      h=3, atr_period=14)
        self.assertGreater(stats["n"], 0)
        self.assertGreater(stats["mean_ret_r"], 0.0)

    def test_nonoverlap_dedupes_clustered_events(self):
        # a generator that fires every bar; with h=5 nonoverlap keeps ~1/5
        candles = [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(60)]

        def every_bar(h1, params):
            return [(i, "LONG") for i in range(20, len(h1) - 1)]

        stats = score_signal_on_asset(candles, every_bar, {}, h=5, atr_period=14)
        # ~ (len-1-20)/5 events, far fewer than the ~39 raw
        self.assertLess(stats["n"], 15)
        self.assertGreater(stats["n"], 0)


class TestScreenSignal(unittest.TestCase):
    def _up_asset(self):
        flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(30)]
        up = [Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                     100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(20)]
        return flat + up

    def test_drops_assets_below_min_events(self):
        from moonface.research.edge.signals import donchian_break
        pool = {f"A{j}": self._up_asset() for j in range(10)}
        # tiny asset with no events
        pool["DEAD"] = [Candle(i * H4, 100, 100, 100, 100, 1.0) for i in range(5)]
        result = screen_signal("donchian_break", donchian_break, {"n": 10},
                               pool, h=3, atr_period=14, floor=0.5,
                               min_events=1, min_assets=8)
        self.assertNotIn("DEAD", [a["sym"] for a in result["assets"]])
        self.assertIn(result["verdict"]["verdict"],
                      ("mechanism_exists", "mechanism_does_not_exist",
                       "inconclusive"))

    def test_result_carries_signal_identity(self):
        from moonface.research.edge.signals import donchian_break
        pool = {f"A{j}": self._up_asset() for j in range(9)}
        result = screen_signal("donchian_break", donchian_break, {"n": 10},
                               pool, h=3, atr_period=14, floor=0.5,
                               min_events=1, min_assets=8)
        self.assertEqual(result["signal"], "donchian_break")
        self.assertEqual(result["params"], {"n": 10})
