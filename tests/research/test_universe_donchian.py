# tests/test_universe_donchian.py
import unittest

from moonface.core.metrics import COST_FRACTION
from moonface.research.universe_data import DailyRow
from moonface.research import universe_donchian as ud
from moonface.research.universe_donchian import (GROSS, Position,
                                                  simulate_portfolio)
from moonface.research.universe_donchian import (
    control_for, dominates, evaluate_dominant, stage1_of, stage4_of,
    universe_donchian_specs, N_TRIALS)


def _row(day, qv, close=10.0):
    # day is an integer day-offset; ts_ms = 2021-01-01 + day days
    return DailyRow(ts_ms=1_609_459_200_000 + day * 86_400_000, close=close, quote_volume=qv)


class TestScreener(unittest.TestCase):
    def test_is_alt_perp_excludes_majors_and_stables(self):
        self.assertTrue(ud.is_alt_perp("SOLUSDT"))
        self.assertFalse(ud.is_alt_perp("BTCUSDT"))
        self.assertFalse(ud.is_alt_perp("ETHUSDT"))
        self.assertFalse(ud.is_alt_perp("USDCUSDT"))
        self.assertFalse(ud.is_alt_perp("BTCUSDT_230929"))  # dated future
        self.assertFalse(ud.is_alt_perp("SOLBUSD"))         # non-USDT quote

    def test_expansion_ratio_median_of_prior_window(self):
        rows = [_row(d, qv) for d, qv in
                enumerate([10, 10, 10, 10, 40])]  # last day spikes 4x
        # asof = day 4; prior window (day 0..3) median = 10; ratio = 40/10
        self.assertAlmostEqual(
            ud.expansion_ratio(rows, rows[-1].ts_ms, lookback_days=30), 4.0)

    def test_expansion_ratio_none_when_short_history(self):
        rows = [_row(0, 10.0), _row(1, 20.0)]  # only 1 prior day
        self.assertIsNone(ud.expansion_ratio(rows, rows[-1].ts_ms, 30))

    def test_screen_universe_top_n_by_ratio_with_filters(self):
        # SYMA: high expansion, qualifies; SYMB: low expansion, qualifies;
        # SYMC: fails liquidity floor; SYMD: fails listing-age floor.
        daily = {
            "SYMAUSDT": [_row(d, q) for d, q in
                         enumerate([25e6] * 100 + [5e7])],     # old + liquid + spike
            "SYMBUSDT": [_row(d, q) for d, q in
                         enumerate([25e6] * 100 + [1e7])],     # old + liquid, small spike
            "SYMCUSDT": [_row(d, 1e3) for d in range(101)],     # old but illiquid
            "SYMDUSDT": [_row(d, 5e7) for d in range(5)],       # liquid but too young
        }
        asof = 1_609_459_200_000 + 100 * 86_400_000
        cfg = {"top_n": 5, "lookback_days": 30, "metric": "ratio",
               "min_liquidity_usd": 20e6, "min_age_days": 90, "rank": "expansion"}
        got = ud.screen_universe(daily, asof, cfg)
        self.assertEqual(got, ["SYMAUSDT", "SYMBUSDT"])  # C illiquid, D too young

    def test_screen_universe_static_returns_all_qualifiers(self):
        daily = {"AUSDT": [_row(d, 5e7) for d in range(101)],
                 "BUSDT": [_row(d, 5e7) for d in range(101)]}
        asof = 1_609_459_200_000 + 100 * 86_400_000
        cfg = {"top_n": 5, "lookback_days": 30, "metric": "ratio",
               "min_liquidity_usd": 20e6, "min_age_days": 90, "rank": "static"}
        self.assertEqual(ud.screen_universe(daily, asof, cfg), ["AUSDT", "BUSDT"])

    def test_build_membership_weekly_hold_and_one_day_lag(self):
        # Two symbols alternate which has the bigger spike; membership should
        # hold a set for 7 days then switch, and day-i membership reflects a
        # screen computed strictly before i (no same-day lookahead).
        daily = {
            "AUSDT": [_row(d, (1e8 if d % 14 < 7 else 1e6)) for d in range(30)],
            "BUSDT": [_row(d, (1e6 if d % 14 < 7 else 1e8)) for d in range(30)],
        }
        cal = sorted({r.ts_ms for rs in daily.values() for r in rs})
        cfg = {"top_n": 1, "lookback_days": 30, "metric": "ratio",
               "min_liquidity_usd": 0.0, "min_age_days": 0, "rank": "expansion"}
        membership, book = ud.build_membership(daily, cal, cfg, rebalance_days=7)
        self.assertEqual(set(membership.keys()), set(cal))
        self.assertTrue(all(v == 1 for v in book.values()))  # top_n=1 throughout
        # Membership is constant within each 7-day block (held between rebuilds).
        block0 = {membership[t] for t in cal[:7]}
        self.assertEqual(len(block0), 1)


class TestPortfolioSim(unittest.TestCase):
    def _days(self, n, base=1_609_459_200_000):
        return [base + i * 86_400_000 for i in range(n)]

    def test_flat_portfolio_is_zero(self):
        cal = self._days(5)
        membership = {t: frozenset() for t in cal}
        book = {t: 5 for t in cal}
        r = simulate_portfolio(cal, membership, book, {}, {}, {}, GROSS)
        self.assertEqual(r, [0.0, 0.0, 0.0, 0.0, 0.0])

    def test_single_long_earns_price_move_minus_costs_and_funding(self):
        # ALTS: eligible every day (top_n=1, f_slot=G/1=1.0). One long position
        # entered on day 0 (earns from day 1), exited on day 3. Closes step +10%
        # per day. Daily funding sum 0.001 (long pays).
        cal = self._days(5)
        closes = {10.0, 11.0, 12.1, 13.31, 14.641}  # +10% daily
        daily_close = {"ALTSUSDT": dict(zip(cal, closes))}
        daily_funding = {"ALTSUSDT": {t: 0.001 for t in cal}}
        membership = {t: frozenset({"ALTSUSDT"}) for t in cal}
        book = {t: 1 for t in cal}                    # f_slot = 1.0
        positions = {"ALTSUSDT": [Position("BUY", cal[0], cal[3], 1.0)]}
        r = simulate_portfolio(cal, membership, book, positions,
                               daily_close, daily_funding, GROSS)
        # Position earns days 1,2,3 (entry_day < d <= exit_day). Each = +10% price
        # return - funding 0.001. Entry cost on day1 + exit cost on day3,
        # each one-way = COST_FRACTION/2.
        one_way = COST_FRACTION / 2
        exp1 = (11.0 / 10.0 - 1.0) - 0.001 - one_way   # day1: price - fund - entry cost
        exp2 = (12.1 / 11.0 - 1.0) - 0.001             # day2: price - fund
        exp3 = (13.31 / 12.1 - 1.0) - 0.001 - one_way  # day3: price - fund - exit cost
        self.assertAlmostEqual(r[1], exp1)
        self.assertAlmostEqual(r[2], exp2)
        self.assertAlmostEqual(r[3], exp3)
        self.assertEqual(r[4], 0.0)                    # closed after day3

    def test_position_not_held_when_symbol_ineligible_at_entry(self):
        cal = self._days(4)
        daily_close = {"ALTSUSDT": {cal[0]: 10.0, cal[1]: 11.0, cal[2]: 12.1, cal[3]: 13.31}}
        # NOT eligible at entry day 0 -> capital never deployed.
        membership = {t: frozenset() for t in cal}
        book = {t: 1 for t in cal}
        positions = {"ALTSUSDT": [Position("BUY", cal[0], cal[3], 1.0)]}
        r = simulate_portfolio(cal, membership, book, positions,
                               daily_close, {}, GROSS)
        self.assertEqual(r[1:], [0.0, 0.0, 0.0])

    def test_short_pays_negative_funding(self):
        cal = self._days(3)
        daily_close = {"XUSDT": {cal[0]: 10.0, cal[1]: 9.0, cal[2]: 8.1}}  # -10%/day
        daily_funding = {"XUSDT": {t: 0.001 for t in cal}}
        membership = {t: frozenset({"XUSDT"}) for t in cal}
        book = {t: 1 for t in cal}
        positions = {"XUSDT": [Position("SELL", cal[0], cal[2], 1.0)]}
        r = simulate_portfolio(cal, membership, book, positions,
                               daily_close, daily_funding, GROSS)
        # short on a falling day is a gain; short RECEIVES +funding -> +0.001
        exp1 = -(9.0 / 10.0 - 1.0) + 0.001 - COST_FRACTION / 2
        self.assertAlmostEqual(r[1], exp1)


class TestSpecsEvaluators(unittest.TestCase):
    def test_four_treatment_specs_share_frozen_engine(self):
        specs = universe_donchian_specs()
        self.assertEqual(len(specs), N_TRIALS)
        for s in specs:
            self.assertEqual(s.domain, "universe_donchian")
            self.assertEqual(s.entry["family"], "volexp_donchian")
            self.assertEqual(s.exit["name"], "donchian_trail")
            self.assertEqual(s.exit["params"],
                             {"entry_n": 40, "trail_n": 20, "atr_period": 14, "k_stop": 2.0})
            self.assertEqual(s.fraction, 1.0)

    def test_control_is_static_basket_same_filters(self):
        spec = universe_donchian_specs()[0]
        ctrl = control_for(spec)
        self.assertEqual(ctrl.entry["params"]["rank"], "static")
        # same filters, same engine, same fraction; only rank differs
        for k in ("min_liquidity_usd", "min_age_days", "lookback_days"):
            self.assertEqual(ctrl.entry["params"][k], spec.entry["params"][k])

    def test_dominance_strict_both_metrics(self):
        self.assertTrue(dominates(1.5, 1.1, 1.0, 1.0))
        self.assertFalse(dominates(1.5, 0.9, 1.0, 1.0))   # Sharpe loses
        self.assertFalse(dominates(0.5, 1.1, 1.0, 1.0))   # MAR loses

    def test_stage1_uses_pooled_trades(self):
        m = {"screen_trades": 30, "screen_expectancy_r": 0.01}
        self.assertTrue(stage1_of(m))
        m2 = {"screen_trades": 29, "screen_expectancy_r": 0.5}
        self.assertFalse(stage1_of(m2))                   # too few trades
        m3 = {"screen_trades": 100, "screen_expectancy_r": -0.01}
        self.assertFalse(stage1_of(m3))                   # negative expectancy

    def test_evaluate_dominant_splits_at_fence(self):
        # 10 daily returns (idx 0..9); fence at 8 -> holdout = research[5:8].
        # Treatment returns VARY (so Sharpe>0) and are positive; control flat.
        t_ret = [0.0, 0.010, 0.020, 0.015, 0.025, 0.010, 0.020, 0.015, 0.012, 0.018]
        c_ret = [0.0] * 10
        pooled = [0.5] * 50             # >= 30 trades, positive expectancy
        m = evaluate_dominant(t_ret, c_ret, pooled, fence_idx=8, screen_fraction=0.7)
        self.assertTrue(m["holdout_dominance"])
        self.assertGreater(m["holdout_treatment_mar"], m["holdout_control_mar"])
        self.assertEqual(m["screen_trades"], 50)
        self.assertGreater(m["screen_expectancy_r"], 0.0)
        self.assertIn("research_sharpe", m)

    def test_stage4_lockbox_gate(self):
        tail = {"tail_trades": 10, "tail_treatment_mar": 1.0,
                "tail_treatment_dd": -0.1, "tail_dominance": True}
        self.assertTrue(stage4_of(tail))
        bad = dict(tail, tail_treatment_mar=0.5)
        self.assertFalse(stage4_of(bad))


if __name__ == "__main__":
    unittest.main()
