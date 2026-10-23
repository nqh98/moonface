# tests/test_bab.py
import unittest

from moonface.research.universe_data import DailyRow
from moonface.research.bab import (beta_signal, index_returns, _rebalance,
                                   return_series, simulate)

DAY = 86_400_000


def _rows(closes, qvol=1000.0, start_day=0):
    return [DailyRow((start_day + i) * DAY, c, qvol)
            for i, c in enumerate(closes)]


class TestReturnSeries(unittest.TestCase):
    def test_one_day_returns_on_calendar(self):
        closes = {r.ts_ms: r for r in _rows([100.0, 110.0, 121.0])}
        cal = [0, DAY, 2 * DAY]
        got = return_series(closes, cal)
        self.assertAlmostEqual(got[DAY], 0.1)
        self.assertAlmostEqual(got[2 * DAY], 0.1)
        self.assertNotIn(0, got)  # first calendar day has no prior

    def test_missing_close_breaks_the_pair(self):
        closes = {0: _rows([100.0])[0], 2 * DAY: _rows([121.0])[0]}
        cal = [0, DAY, 2 * DAY]
        got = return_series(closes, cal)
        self.assertEqual(got, {})  # day 1 and day 2 each miss one leg


class TestBetaSignal(unittest.TestCase):
    def _series(self, scale):
        # 24 deterministic-but-varying index returns; symbol = scale * index
        idx = {(i + 1) * DAY: 0.01 * ((i % 5) - 2) for i in range(24)}
        sym = {t: scale * r for t, r in idx.items()}
        return sym, idx

    def test_beta_recovers_scale(self):
        sym, idx = self._series(2.0)
        self.assertAlmostEqual(beta_signal(sym, idx, 24 * DAY, 60), 2.0)
        sym_low, idx2 = self._series(0.5)
        self.assertAlmostEqual(beta_signal(sym_low, idx2, 24 * DAY, 60), 0.5)

    def test_insufficient_points_returns_none(self):
        sym, idx = self._series(1.0)
        self.assertIsNone(beta_signal(sym, idx, 24 * DAY, 60, min_points=50))

    def test_zero_index_variance_returns_none(self):
        idx = {(i + 1) * DAY: 0.0 for i in range(24)}
        sym = {t: 0.01 for t in idx}
        self.assertIsNone(beta_signal(sym, idx, 24 * DAY, 60))


class TestIndexReturns(unittest.TestCase):
    def test_equal_weight_mean_of_members(self):
        rets = {"A": {DAY: 0.02}, "B": {DAY: 0.04}, "C": {DAY: 0.10}}
        members = {(1970, 1): ["A", "B"]}  # C excluded from membership
        got = index_returns(rets, members, [DAY])
        self.assertAlmostEqual(got[DAY], 0.03)


class TestRebalance(unittest.TestCase):
    def _beta_world(self):
        idx = {(i + 1) * DAY: 0.01 * ((i % 5) - 2) for i in range(24)}
        rets = {
            "LO1": {t: 0.5 * r for t, r in idx.items()},
            "LO2": {t: 0.5 * r for t, r in idx.items()},
            "HI1": {t: 2.0 * r for t, r in idx.items()},
            "HI2": {t: 2.0 * r for t, r in idx.items()},
        }
        return rets, idx

    def test_long_low_beta_short_high_beta_neutral_weights(self):
        rets, idx = self._beta_world()
        book = _rebalance(["LO1", "LO2", "HI1", "HI2"], rets, idx,
                          lookback_days=60, ts=24 * DAY, k=2)
        # low-beta names long, high-beta names short
        self.assertGreater(book["LO1"], 0.0)
        self.assertGreater(book["LO2"], 0.0)
        self.assertLess(book["HI1"], 0.0)
        self.assertLess(book["HI2"], 0.0)
        # beta-neutral: long leg sum*betaL == short leg |sum|*betaH == 1
        long_beta_exposure = (book["LO1"] + book["LO2"]) * 0.5
        short_beta_exposure = (book["HI1"] + book["HI2"]) * 2.0
        self.assertAlmostEqual(long_beta_exposure, 1.0)
        self.assertAlmostEqual(short_beta_exposure, -1.0)

    def test_too_few_scored_names_returns_empty(self):
        rets, idx = self._beta_world()
        book = _rebalance(["LO1", "HI1"], rets, idx, lookback_days=60,
                          ts=24 * DAY, k=2)
        self.assertEqual(book, {})


class TestSimulate(unittest.TestCase):
    def test_produces_dated_return_series_without_lookahead(self):
        # 80 calendar days; two persistent low-beta and two high-beta names.
        n = 80
        base = [100.0]
        for i in range(1, n):
            base.append(base[-1] * (1.0 + 0.01 * ((i % 5) - 2)))
        lo = [100.0]
        hi = [100.0]
        for i in range(1, n):
            mkt = 0.01 * ((i % 5) - 2)
            lo.append(lo[-1] * (1.0 + 0.5 * mkt))
            hi.append(hi[-1] * (1.0 + 2.0 * mkt))
        daily = {
            "LO1": _rows(lo), "LO2": _rows(lo),
            "HI1": _rows(hi), "HI2": _rows(hi),
        }
        series = simulate(daily, funding={}, lookback_days=60, start_ms=0,
                          end_ms=n * DAY, top_n=4, quintile=2,
                          rebalance_days=7, fee=0.0005,
                          min_history_days=10, vol_days=10)
        self.assertTrue(series)
        self.assertTrue(all(isinstance(ts, int) for ts, _ in series))
        # warmup: no beta until 20 overlapping returns exist -> early flat
        self.assertEqual(series[0][1], 0.0)


if __name__ == "__main__":
    unittest.main()
