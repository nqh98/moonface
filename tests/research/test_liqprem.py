# tests/test_liqprem.py
import unittest

from moonface.research.universe_data import DailyRow
from moonface.research.liqprem import (_leg_fee, _rebalance, amihud_signal,
                                       build_viability_universe, simulate)

DAY = 86_400_000


class TestAmihudSignal(unittest.TestCase):
    def _world(self, qvol):
        rets = {i * DAY: 0.02 for i in range(1, 41)}
        closes = {i * DAY: DailyRow(i * DAY, 100.0, qvol) for i in range(1, 41)}
        return rets, closes

    def test_mean_of_abs_return_over_dollar_volume(self):
        rets, closes = self._world(1000.0)
        # every day contributes |0.02| / 1000 = 2e-05
        self.assertAlmostEqual(
            amihud_signal(rets, closes, 40 * DAY, 30), 2e-05)

    def test_illiquid_symbol_scores_higher(self):
        thin_r, thin_c = self._world(100.0)
        deep_r, deep_c = self._world(100_000.0)
        thin = amihud_signal(thin_r, thin_c, 40 * DAY, 30)
        deep = amihud_signal(deep_r, deep_c, 40 * DAY, 30)
        self.assertGreater(thin, deep)

    def test_window_is_trailing_and_inclusive_of_ts(self):
        rets = {DAY: 1.0, 2 * DAY: 0.0}
        closes = {DAY: DailyRow(DAY, 100.0, 1.0),
                  2 * DAY: DailyRow(2 * DAY, 100.0, 1.0)}
        # days=1 ending at 2*DAY sees only 2*DAY -> |0.0|/1.0 = 0.0
        self.assertAlmostEqual(
            amihud_signal(rets, closes, 2 * DAY, 1, min_points=1), 0.0)

    def test_too_few_points_returns_none(self):
        rets, closes = self._world(1000.0)
        self.assertIsNone(amihud_signal(rets, closes, 5 * DAY, 30))

    def test_zero_volume_days_are_dropped_not_infinite(self):
        rets = {i * DAY: 0.02 for i in range(1, 41)}
        closes = {i * DAY: DailyRow(i * DAY, 100.0,
                                    0.0 if i == 40 else 1000.0)
                  for i in range(1, 41)}
        self.assertAlmostEqual(
            amihud_signal(rets, closes, 40 * DAY, 30), 2e-05)


def _rows(n, qvol, start_day=0):
    return [DailyRow((start_day + i) * DAY, 100.0, qvol) for i in range(n)]


class TestViabilityUniverse(unittest.TestCase):
    def test_admits_every_symbol_over_the_floor_not_just_top_n(self):
        daily = {"DEEP": _rows(400, 50_000_000.0),
                 "MID": _rows(400, 5_000_000.0),
                 "THIN": _rows(400, 1_500_000.0)}
        got = build_viability_universe(daily, 399 * DAY, 365, 30, 1_000_000.0)
        self.assertEqual(got, ["DEEP", "MID", "THIN"])

    def test_below_volume_floor_is_excluded(self):
        daily = {"OK": _rows(400, 2_000_000.0),
                 "DUST": _rows(400, 100_000.0)}
        got = build_viability_universe(daily, 399 * DAY, 365, 30, 1_000_000.0)
        self.assertEqual(got, ["OK"])

    def test_too_young_is_excluded(self):
        daily = {"OLD": _rows(400, 2_000_000.0),
                 "NEW": _rows(30, 2_000_000.0, start_day=370)}
        got = build_viability_universe(daily, 399 * DAY, 365, 30, 1_000_000.0)
        self.assertEqual(got, ["OLD"])

    def test_floor_uses_median_so_one_spike_day_does_not_qualify(self):
        # 29 days at $10k plus one $100M print: mean clears $1M, median does not
        rows = [DailyRow(i * DAY, 100.0, 10_000.0) for i in range(400)]
        rows[399] = DailyRow(399 * DAY, 100.0, 100_000_000.0)
        got = build_viability_universe({"SPIKE": rows}, 399 * DAY,
                                       365, 30, 1_000_000.0)
        self.assertEqual(got, [])

    def test_no_rows_in_window_is_excluded(self):
        daily = {"STALE": _rows(10, 5_000_000.0)}
        got = build_viability_universe(daily, 399 * DAY, 0, 30, 1_000_000.0)
        self.assertEqual(got, [])


class TestRebalance(unittest.TestCase):
    def _world(self):
        """5 symbols, beta ~= 1 for all, identical returns; only dollar volume
        differs -> Amihud ranking is purely the liquidity ordering."""
        n = 60
        idx = {(i + 1) * DAY: 0.01 * ((i % 5) - 2) for i in range(n)}
        vols = {"A": 1_000.0, "B": 10_000.0, "C": 100_000.0,
                "D": 1_000_000.0, "E": 10_000_000.0}
        rets, closes = {}, {}
        for sym, qv in vols.items():
            rets[sym] = dict(idx)
            closes[sym] = {t: DailyRow(t, 100.0, qv) for t in idx}
        return rets, closes, idx

    def test_longs_the_illiquid_and_shorts_the_liquid(self):
        rets, closes, idx = self._world()
        book = _rebalance(["A", "B", "C", "D", "E"], rets, closes, idx,
                          60 * DAY, quintile=5, lookback_days=60,
                          amihud_days=30)
        self.assertGreater(book["A"], 0.0)   # thinnest -> long
        self.assertLess(book["E"], 0.0)      # deepest  -> short
        self.assertNotIn("C", book)          # middle quintiles unheld

    def test_book_is_empty_when_universe_too_small(self):
        rets, closes, idx = self._world()
        book = _rebalance(["A"], rets, closes, idx, 60 * DAY,
                          quintile=5, lookback_days=60, amihud_days=30)
        self.assertEqual(book, {})

    def test_legs_are_beta_scaled_when_betas_are_positive(self):
        rets, closes, idx = self._world()
        book = _rebalance(["A", "B", "C", "D", "E"], rets, closes, idx,
                          60 * DAY, quintile=5, lookback_days=60,
                          amihud_days=30)
        # betas are all ~1 here, so the two legs scale to equal magnitude
        self.assertAlmostEqual(book["A"], -book["E"], places=6)

    def test_symbol_without_amihud_score_is_dropped(self):
        rets, closes, idx = self._world()
        closes["A"] = {}  # no volume rows -> amihud_signal returns None
        book = _rebalance(["A", "B", "C", "D", "E"], rets, closes, idx,
                          60 * DAY, quintile=5, lookback_days=60,
                          amihud_days=30)
        self.assertNotIn("A", book)


class TestLegFee(unittest.TestCase):
    def test_long_leg_pays_the_illiquid_rate(self):
        self.assertEqual(
            _leg_fee("A", {"A": 0.5}, {}, 0.0025, 0.0005), 0.0025)

    def test_short_leg_pays_the_liquid_rate(self):
        self.assertEqual(
            _leg_fee("E", {"E": -0.5}, {}, 0.0025, 0.0005), 0.0005)

    def test_exiting_symbol_pays_the_rate_of_the_leg_it_leaves(self):
        # absent from the new book -> classified by its old weight
        self.assertEqual(
            _leg_fee("A", {}, {"A": 0.5}, 0.0025, 0.0005), 0.0025)
        self.assertEqual(
            _leg_fee("E", {}, {"E": -0.5}, 0.0025, 0.0005), 0.0005)


class TestSimulate(unittest.TestCase):
    def _daily(self, n=200):
        vols = {"A": 1_100_000.0, "B": 3_000_000.0, "C": 8_000_000.0,
                "D": 20_000_000.0, "E": 60_000_000.0}
        daily = {}
        for sym, qv in vols.items():
            closes, px = [], 100.0
            for i in range(n):
                px *= 1.0 + 0.01 * ((i % 5) - 2)
                closes.append(DailyRow(i * DAY, px, qv))
            daily[sym] = closes
        return daily

    def _run(self, fee_il, fee_li):
        return simulate(
            self._daily(), {}, start_ms=0, end_ms=200 * DAY, quintile=5,
            rebalance_days=7, fee_illiquid=fee_il, fee_liquid=fee_li,
            min_history_days=0, vol_days=30,
            min_median_dollar_vol=1_000_000.0, lookback_days=60,
            amihud_days=30)

    def test_returns_one_row_per_calendar_day_after_the_first(self):
        out = self._run(0.0, 0.0)
        self.assertEqual(len(out), 199)
        self.assertTrue(all(isinstance(t, int) for t, _ in out))

    def test_punitive_costs_lower_the_mean_return(self):
        gross = sum(r for _, r in self._run(0.0, 0.0))
        net = sum(r for _, r in self._run(0.0025, 0.0005))
        self.assertLess(net, gross)

    def test_asymmetric_costs_bite_harder_than_symmetric_cheap_ones(self):
        cheap = sum(r for _, r in self._run(0.0005, 0.0005))
        punitive = sum(r for _, r in self._run(0.0025, 0.0005))
        self.assertLess(punitive, cheap)

    def test_funding_is_charged_against_weights(self):
        daily = self._daily()
        funding = {"A": {i * DAY: 0.001 for i in range(200)}}
        with_f = simulate(
            daily, funding, start_ms=0, end_ms=200 * DAY, quintile=5,
            rebalance_days=7, fee_illiquid=0.0, fee_liquid=0.0,
            min_history_days=0, vol_days=30,
            min_median_dollar_vol=1_000_000.0, lookback_days=60,
            amihud_days=30)
        without = self._run(0.0, 0.0)
        self.assertLess(sum(r for _, r in with_f),
                        sum(r for _, r in without))


if __name__ == "__main__":
    unittest.main()
