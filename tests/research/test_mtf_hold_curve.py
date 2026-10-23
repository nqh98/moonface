import unittest

from moonface.core.models import Candle
from moonface.research.mtf.grid import broaden_best_cell
from moonface.research.mtf.hold_curve import (forward_path, long_horizon_scan,
                                              optimal_hold)


def _c(close: float, i: int) -> Candle:
    return Candle(timestamp_ms=i * 900_000, open=close, high=close + 1,
                  low=close - 1, close=close, volume=1.0)


class OptimalHoldTest(unittest.TestCase):
    def _rows(self, means, zs):
        # days/marginal don't drive optimal_hold; only mean_r + z do
        return [{"h": int(d * 96), "days": d, "n": 100, "mean_r": m, "z": z,
                 "marg_per_day": 0.0}
                for d, m, z in zip([0.5, 1.0, 1.5, 2.0, 3.0], means, zs)]

    def test_picks_risk_adjusted_peak_not_raw_mean_peak(self):
        # raw E[R] peaks at 3.0d (noisy tail); risk-adjusted z peaks at 1.5d
        rows = self._rows(means=[0.1, 0.4, 0.7, 0.6, 0.9],
                          zs=[0.3, 0.9, 1.6, 1.1, 0.5])
        pick = optimal_hold(rows)
        self.assertEqual(pick["hold_days"], 1.5)      # argmax z
        self.assertEqual(pick["hold_bars"], 144)
        self.assertEqual(pick["raw_peak_days"], 3.0)  # argmax mean, reported apart
        self.assertTrue(pick["significant"])          # |z|=1.6 >= 1.0

    def test_short_horizon_noise_blip_does_not_capture_the_pick(self):
        # a big negative mean blip at 0.5d must not fool the selector (the failure
        # mode of a marginal-<=0 rule); z still peaks at 2.0d
        rows = self._rows(means=[-0.5, 0.2, 0.5, 0.8, 0.6],
                          zs=[-0.4, 0.5, 1.0, 1.5, 0.9])
        pick = optimal_hold(rows)
        self.assertEqual(pick["hold_days"], 2.0)

    def test_significance_flag_respects_floor(self):
        rows = self._rows(means=[0.1, 0.2, 0.3, 0.2, 0.1],
                          zs=[0.2, 0.4, 0.6, 0.5, 0.3])
        pick = optimal_hold(rows, z_floor=1.0)
        self.assertEqual(pick["hold_days"], 1.5)
        self.assertFalse(pick["significant"])         # peak z 0.6 < 1.0


class ForwardPathContractTest(unittest.TestCase):
    def test_constant_n_and_monotone_drift_on_a_clean_ramp(self):
        # a long steady uptrend so the gate+entry fire; every kept trade is scored
        # at all horizons -> constant n, and forward R grows with the horizon.
        candles = [_c(100.0 + 0.05 * i, i) for i in range(6000)]
        rows = forward_path(candles, broaden_best_cell(), [96, 192, 288])
        self.assertEqual([r["h"] for r in rows], [96, 192, 288])
        ns = {r["n"] for r in rows}
        self.assertEqual(len(ns), 1)                  # same trade set at every h
        if rows[0]["n"] > 0:                          # if the gate fired at all
            self.assertLess(rows[0]["mean_r"], rows[-1]["mean_r"])  # drift grows

    def test_long_scan_uses_larger_n_at_shorter_holds(self):
        # per-horizon sampling: a shorter hold packs in strictly more independent
        # trades than a longer one (spacing = the horizon), and longs+shorts = n
        candles = [_c(100.0 + 0.05 * i, i) for i in range(8000)]
        rows = long_horizon_scan(candles, broaden_best_cell(), [96, 480])
        self.assertEqual([r["h"] for r in rows], [96, 480])
        for r in rows:
            self.assertEqual(r["longs"] + r["shorts"], r["n"])
        if rows[1]["n"] > 0:
            self.assertGreater(rows[0]["n"], rows[1]["n"])  # 1d sample > 5d sample


if __name__ == "__main__":
    unittest.main()
