# tests/test_resrev.py
import unittest

from moonface.research.universe_data import DailyRow
from moonface.research.resrev import (_rebalance, mean_z, residual_signal,
                                      simulate)

DAY = 86_400_000


def _rows(closes, qvol=1000.0, start_day=0):
    return [DailyRow((start_day + i) * DAY, c, qvol)
            for i, c in enumerate(closes)]


class TestResidualSignal(unittest.TestCase):
    def test_residual_is_return_minus_beta_times_index(self):
        ret = {DAY: 0.02}
        idx = {DAY: 0.01}
        self.assertAlmostEqual(residual_signal(ret, 1.5, idx, DAY), 0.005)

    def test_missing_inputs_return_none(self):
        self.assertIsNone(residual_signal({}, 1.0, {DAY: 0.01}, DAY))
        self.assertIsNone(residual_signal({DAY: 0.02}, None, {DAY: 0.01}, DAY))
        self.assertIsNone(residual_signal({DAY: 0.02}, 1.0, {}, DAY))


class TestMeanZ(unittest.TestCase):
    def test_positive_drift_has_positive_z(self):
        m, z = mean_z([0.01, 0.02, 0.015, 0.005, 0.012])
        self.assertGreater(m, 0.0)
        self.assertGreater(z, 0.0)

    def test_negative_mean_has_negative_z(self):
        m, z = mean_z([-0.01, -0.02, 0.0, -0.015])
        self.assertLess(m, 0.0)
        self.assertLess(z, 0.0)

    def test_empty_is_zero(self):
        self.assertEqual(mean_z([]), (0.0, 0.0))


class TestRebalance(unittest.TestCase):
    def _world(self):
        # beta ~= 1 for all; idiosyncratic shock only on the decision day so
        # residuals at ts rank A<B<C<D (A most negative -> long).
        n = 24
        idx = {(i + 1) * DAY: 0.01 * ((i % 5) - 2) for i in range(n)}
        rets = {}
        shock = {"A": -0.05, "B": -0.04, "C": 0.04, "D": 0.05}
        for sym, s in shock.items():
            r = {t: v for t, v in idx.items()}  # beta 1, residual 0...
            r[n * DAY] = idx[n * DAY] + s        # ...except the decision day
            rets[sym] = r
        return rets, idx

    def test_long_low_residual_short_high_residual(self):
        rets, idx = self._world()
        book = _rebalance(["A", "B", "C", "D"], rets, idx,
                          lookback_days=60, ts=24 * DAY, k=2)
        self.assertGreater(book["A"], 0.0)
        self.assertGreater(book["B"], 0.0)
        self.assertLess(book["C"], 0.0)
        self.assertLess(book["D"], 0.0)

    def test_too_few_scored_returns_empty(self):
        rets, idx = self._world()
        book = _rebalance(["A", "D"], rets, idx, lookback_days=60,
                          ts=24 * DAY, k=2)
        self.assertEqual(book, {})


class TestSimulate(unittest.TestCase):
    def test_produces_dated_series_and_warmup_is_flat(self):
        n = 90
        idx_path = [0.01 * ((i % 5) - 2) for i in range(n)]
        syms = {}
        for name, beta, phase in [("A", 1.0, 0), ("B", 1.0, 1),
                                  ("C", 1.0, 2), ("D", 1.0, 3)]:
            closes = [100.0]
            for i in range(1, n):
                # market component + small rotating idiosyncratic shock
                idio = 0.02 * (1 if (i % 4) == phase else -0.3)
                closes.append(closes[-1] * (1.0 + beta * idx_path[i] + idio))
            syms[name] = _rows(closes)
        series = simulate(syms, funding={}, lookback_days=60, start_ms=0,
                          end_ms=n * DAY, top_n=4, decile=2, rebalance_days=1,
                          fee=0.0005, min_history_days=10, vol_days=10)
        self.assertTrue(series)
        self.assertTrue(all(isinstance(ts, int) for ts, _ in series))
        self.assertEqual(series[0][1], 0.0)  # no beta until warmup completes


if __name__ == "__main__":
    unittest.main()
