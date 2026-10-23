from __future__ import annotations

import unittest


class SimulateEquityTest(unittest.TestCase):
    def test_compounds_ordered_stream(self) -> None:
        from moonface.research.sizing import simulate_equity
        # 1 * (1+0.1*1) * (1+0.1*-1) * (1+0.1*2) = 1.1 * 0.9 * 1.2 = 1.188
        stats = simulate_equity([1.0, -1.0, 2.0], f=0.1)
        self.assertAlmostEqual(stats.terminal, 1.188, places=6)
        self.assertEqual(stats.n_trades, 3)
        # peak 1.1 then 0.99 -> drawdown (1.1-0.99)/1.1*100 = 10.0
        self.assertAlmostEqual(stats.max_drawdown_pct, 10.0, places=4)

    def test_ruin_zeroes_equity(self) -> None:
        from moonface.research.sizing import simulate_equity
        # 1 + 0.6 * -2.0 = -0.2 <= 0 -> ruin
        stats = simulate_equity([-2.0], f=0.6)
        self.assertEqual(stats.terminal, 0.0)
        self.assertEqual(stats.max_drawdown_pct, 100.0)

    def test_cagr_none_without_span(self) -> None:
        from moonface.research.sizing import simulate_equity
        self.assertIsNone(simulate_equity([1.0], f=0.1, span_days=0.0).cagr)

    def test_cagr_computed_with_span(self) -> None:
        from moonface.research.sizing import simulate_equity
        stats = simulate_equity([1.0], f=0.1, span_days=365.25)
        self.assertAlmostEqual(stats.cagr, 0.1, places=6)  # 1.1 over one year


class MonteCarloDrawdownTest(unittest.TestCase):
    def _stream(self) -> list[float]:
        # mixed wins/losses so drawdown is non-trivial
        return [2.0, -1.0, -1.0, 2.0, -1.0, 2.0, -1.0, -1.0, 2.0, -1.0]

    def test_deterministic_with_seed(self) -> None:
        from moonface.research.sizing import monte_carlo_drawdown
        a = monte_carlo_drawdown(self._stream(), f=0.2, percentile=95,
                                 resamples=300, seed=12345)
        b = monte_carlo_drawdown(self._stream(), f=0.2, percentile=95,
                                 resamples=300, seed=12345)
        self.assertEqual(a, b)

    def test_non_decreasing_in_f(self) -> None:
        from moonface.research.sizing import monte_carlo_drawdown
        rs = self._stream()
        low = monte_carlo_drawdown(rs, 0.1, 95, 300, 12345)
        mid = monte_carlo_drawdown(rs, 0.3, 95, 300, 12345)
        high = monte_carlo_drawdown(rs, 0.5, 95, 300, 12345)
        self.assertLessEqual(low, mid)
        self.assertLessEqual(mid, high)

    def test_empty_stream_is_zero(self) -> None:
        from moonface.research.sizing import monte_carlo_drawdown
        self.assertEqual(monte_carlo_drawdown([], 0.2, 95, 300, 12345), 0.0)


class OptimizeFractionTest(unittest.TestCase):
    def _edge(self) -> list[float]:
        # 60% +2R, 40% -1R: strongly positive expectancy
        return ([2.0, 2.0, 2.0, -1.0, -1.0] * 8)

    def test_positive_edge_picks_nonzero_f(self) -> None:
        from moonface.research.sizing import optimize_fraction
        res = optimize_fraction(self._edge(), dd_cap=0.20, percentile=95,
                                resamples=300, seed=12345)
        self.assertGreater(res.f, 0.0)
        self.assertTrue(res.capped)
        self.assertGreater(res.terminal, 1.0)

    def test_tighter_cap_returns_smaller_f(self) -> None:
        from moonface.research.sizing import optimize_fraction
        loose = optimize_fraction(self._edge(), 0.30, 95, 300, 12345)
        tight = optimize_fraction(self._edge(), 0.05, 95, 300, 12345)
        self.assertLessEqual(tight.f, loose.f)

    def test_losing_stream_returns_zero_f(self) -> None:
        from moonface.research.sizing import optimize_fraction
        losing = [-1.0, -1.0, -1.0, 1.0] * 8  # negative expectancy
        res = optimize_fraction(losing, 0.20, 95, 300, 12345)
        self.assertEqual(res.f, 0.0)
        self.assertFalse(res.capped)

    def test_invalid_args_raise(self) -> None:
        from moonface.research.sizing import optimize_fraction
        with self.assertRaises(ValueError):
            optimize_fraction([1.0], dd_cap=0.0)
        with self.assertRaises(ValueError):
            optimize_fraction([1.0], dd_cap=1.5)
        with self.assertRaises(ValueError):
            optimize_fraction([1.0], percentile=0)
        with self.assertRaises(ValueError):
            optimize_fraction([1.0], resamples=0)
        with self.assertRaises(ValueError):
            optimize_fraction([1.0], f_grid=[])


class SizeReportTest(unittest.TestCase):
    def _edge(self) -> list[float]:
        return ([2.0, 2.0, 2.0, -1.0, -1.0] * 8)

    def test_research_f_reused_on_tail(self) -> None:
        from moonface.research.sizing import size_report, optimize_fraction, simulate_equity
        research = self._edge()
        tail = [2.0, -1.0, 2.0, -1.0, 2.0]
        rep = size_report(research, tail, resamples=300, seed=12345)
        expected_f = optimize_fraction(research, resamples=300, seed=12345).f
        self.assertEqual(rep.chosen_f, expected_f)
        # tail EquityStats must be produced by the research-fit f, not a tail re-fit
        self.assertAlmostEqual(rep.tail.terminal,
                               simulate_equity(tail, expected_f).terminal, places=6)
        self.assertEqual(rep.research.n_trades, len(research))
        self.assertEqual(rep.tail.n_trades, len(tail))

    def test_empty_research_reports_no_trades(self) -> None:
        from moonface.research.sizing import size_report
        rep = size_report([], [1.0, 2.0], resamples=300, seed=12345)
        self.assertEqual(rep.chosen_f, 0.0)
        self.assertEqual(rep.reject_reason, "no research trades to size")

    def test_empty_tail_is_identity(self) -> None:
        from moonface.research.sizing import size_report
        rep = size_report(self._edge(), [], resamples=300, seed=12345)
        self.assertEqual(rep.tail.n_trades, 0)
        self.assertEqual(rep.tail.terminal, 1.0)
        self.assertEqual(rep.tail_mc_drawdown_pct, 0.0)
