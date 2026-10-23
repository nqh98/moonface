import random
import unittest

from moonface.research import fwd_analysis as fa

_DAY_MS = 86_400_000


class BootstrapCITest(unittest.TestCase):
    def test_degenerate_inputs_collapse(self):
        self.assertEqual(fa.bootstrap_expectancy_ci([]), (0.0, 0.0))
        self.assertEqual(fa.bootstrap_expectancy_ci([1.5]), (1.5, 1.5))
        self.assertEqual(fa.bootstrap_expectancy_ci([2.0] * 50), (2.0, 2.0))

    def test_positive_edge_excludes_zero(self):
        rng = random.Random(1)
        rs = [(-2.0 if rng.random() < 0.3 else 4.0) for _ in range(300)]
        lo, hi = fa.bootstrap_expectancy_ci(rs, resamples=2000)
        self.assertGreater(lo, 0.0)
        self.assertLess(lo, hi)

    def test_deterministic(self):
        rs = [(-1.0) ** i * (1 + i % 3) for i in range(60)]
        self.assertEqual(fa.bootstrap_expectancy_ci(rs, resamples=500),
                         fa.bootstrap_expectancy_ci(rs, resamples=500))


class SuccessCriterionTest(unittest.TestCase):
    def test_flat_stream_fails(self):
        rng = random.Random(2)
        rs = [(-2.0 if rng.random() < 0.5 else 2.0) for _ in range(100)]
        self.assertFalse(fa.success_criterion(rs))

    def test_strong_stream_passes(self):
        rs = [4.0, 4.0, -2.0] * 40
        self.assertTrue(fa.success_criterion(rs))


class NullP95ThresholdTest(unittest.TestCase):
    def test_higher_order_statistic_convention(self):
        # Amendment 2 condition 2: sorted[min(n-1, ceil(0.95*n))], 0-based.
        nets = [float(i) for i in range(200)]  # sorted 0..199
        self.assertEqual(fa.null_p95_threshold(nets), 190.0)

    def test_small_n_clamps_to_max(self):
        self.assertEqual(fa.null_p95_threshold([3.0, 1.0, 2.0]), 3.0)

    def test_order_independent(self):
        nets = [5.0, -1.0, 3.0] * 70  # n=210, ceil(199.5)=200
        self.assertEqual(fa.null_p95_threshold(nets), 5.0)


class ForwardSuccessTest(unittest.TestCase):
    STRONG = [4.0, 4.0, -2.0] * 40  # net +240, CI well above 0

    def test_requires_beating_null_p95(self):
        self.assertTrue(fa.forward_success(self.STRONG, null_p95=100.0))
        self.assertFalse(fa.forward_success(self.STRONG, null_p95=240.0))  # strict
        self.assertFalse(fa.forward_success(self.STRONG, null_p95=500.0))

    def test_negative_null_p95_cannot_rescue_losing_stream(self):
        # Amendment 2 condition 1(i): cum R > 0 guards a bad-regime null p95.
        losing = [-2.0, -2.0, 1.0] * 40
        self.assertFalse(fa.forward_success(losing, null_p95=-500.0))


class RuinTest(unittest.TestCase):
    def test_all_losing_hits_any_budget(self):
        p = fa.ruin_probability([-2.0] * 30, budget_r=-4.0,
                                horizon_trades=10, resamples=200)
        self.assertEqual(p, 1.0)

    def test_unreachable_budget(self):
        p = fa.ruin_probability([4.0] * 30, budget_r=-4.0,
                                horizon_trades=10, resamples=200)
        self.assertEqual(p, 0.0)

    def test_demean_raises_risk_for_positive_edge(self):
        rng = random.Random(3)
        rs = [(-2.0 if rng.random() < 0.25 else 4.0) for _ in range(200)]
        kw = dict(budget_r=-20.0, horizon_trades=100, resamples=500)
        self.assertGreaterEqual(fa.ruin_probability(rs, demean=True, **kw),
                                fa.ruin_probability(rs, demean=False, **kw))

    def test_peak_relative_at_least_cumulative(self):
        rng = random.Random(4)
        rs = [(-2.0 if rng.random() < 0.3 else 4.0) for _ in range(200)]
        kw = dict(budget_r=-12.0, horizon_trades=60, resamples=500)
        self.assertGreaterEqual(
            fa.ruin_probability(rs, peak_relative=True, **kw),
            fa.ruin_probability(rs, peak_relative=False, **kw))


class PathStatsTest(unittest.TestCase):
    def test_max_drawdown_and_cumulative_min(self):
        rs = [2.0, -3.0, -1.0, 5.0]
        self.assertEqual(fa.max_drawdown_path(rs), -4.0)
        self.assertEqual(fa.cumulative_min(rs), -2.0)

    def test_time_under_water(self):
        t0 = 1_600_000_000_000
        stream = [(t0, 1.0), (t0 + 1 * _DAY_MS, -2.0),
                  (t0 + 3 * _DAY_MS, 0.5), (t0 + 5 * _DAY_MS, 2.0)]
        # peak after trade 1 at t0; recovered at t0+5d -> 5 days under water
        self.assertEqual(fa.time_under_water_days(stream), 5.0)

    def test_trades_per_year(self):
        t0 = 1_600_000_000_000
        stream = [(t0 + i * _DAY_MS, 0.1) for i in range(366)]
        self.assertAlmostEqual(fa.trades_per_year(stream), 366.0, delta=2.0)


class RequiredNTest(unittest.TestCase):
    def test_point_estimate_power(self):
        # power=0.5 collapses to N = ceil((z_{.975} * sigma / mu)^2)
        self.assertEqual(fa.required_n(0.25, 1.4, power=0.5), 121)

    def test_monotonic_in_power(self):
        self.assertGreater(fa.required_n(0.25, 1.4, power=0.8),
                           fa.required_n(0.25, 1.4, power=0.5))
