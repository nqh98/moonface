# tests/test_research_metrics.py
import math
import unittest

from moonface.core.metrics import MAX_LEVERAGE, equity_summary, deflated_sharpe, expected_max_sharpe


class TestEquitySummary(unittest.TestCase):
    def test_empty_stream(self):
        s = equity_summary([], 0.01)  # empty list: no pairs needed
        self.assertEqual(s.trade_count, 0)
        self.assertEqual(s.net_return, 0.0)
        self.assertEqual(s.max_drawdown, 0.0)
        self.assertEqual(s.mar, 0.0)
        self.assertEqual(s.sharpe, 0.0)

    def test_two_trades_hand_computed(self):
        # f=0.5, rs=[+1R, -1R]: equity 1.0 -> 1.5 -> 0.75.
        # net = -0.25; max drawdown = 0.75/1.5 - 1 = -0.5; MAR = -0.25/0.5 = -0.5.
        s = equity_summary([(1.0, 1.0), (-1.0, 1.0)], 0.5)
        self.assertAlmostEqual(s.net_return, -0.25)
        self.assertAlmostEqual(s.max_drawdown, -0.5)
        self.assertAlmostEqual(s.mar, -0.5)
        self.assertEqual(s.trade_count, 2)

    def test_all_winners_mar_is_inf(self):
        s = equity_summary([(1.0, 1.0), (2.0, 1.0)], 0.01)
        self.assertGreater(s.net_return, 0.0)
        self.assertEqual(s.max_drawdown, 0.0)
        self.assertTrue(math.isinf(s.mar))

    def test_ruin_clamps_to_minus_one(self):
        # 1 + f*r = 1 - 1.5 < 0 -> ruin
        s = equity_summary([(-1.0, 1.0)], 1.5)
        self.assertEqual(s.net_return, -1.0)
        self.assertEqual(s.max_drawdown, -1.0)
        self.assertAlmostEqual(s.mar, -1.0)

    def test_symmetric_stream_has_zero_skew(self):
        s = equity_summary([(1.0, 1.0), (-1.0, 1.0), (1.0, 1.0), (-1.0, 1.0)], 0.01)
        self.assertAlmostEqual(s.skew, 0.0)
        self.assertAlmostEqual(s.kurtosis, 1.0)  # two-point symmetric dist

    def test_sharpe_sign_follows_mean(self):
        up = equity_summary([(1.0, 1.0), (0.5, 1.0), (1.5, 1.0), (0.8, 1.0)], 0.01)
        down = equity_summary([(-1.0, 1.0), (-0.5, 1.0), (-1.5, 1.0), (-0.8, 1.0)], 0.01)
        self.assertGreater(up.sharpe, 0.0)
        self.assertLess(down.sharpe, 0.0)


class TestDeflatedSharpe(unittest.TestCase):
    def test_zero_sr_with_no_deflation_is_half(self):
        # n_trials < 2 -> benchmark SR0 = 0; z = 0 -> Phi(0) = 0.5
        self.assertAlmostEqual(deflated_sharpe(0.0, 100, 0.0, 3.0, [], 1), 0.5)

    def test_monotone_decreasing_in_trial_count(self):
        srs = [0.05, -0.02, 0.01, 0.03]
        d10 = deflated_sharpe(0.3, 200, 0.0, 3.0, srs, 10)
        d1000 = deflated_sharpe(0.3, 200, 0.0, 3.0, srs, 1000)
        self.assertGreater(d10, d1000)

    def test_bounded_probability(self):
        for sr in (-1.0, 0.0, 0.5, 2.0):
            d = deflated_sharpe(sr, 50, 0.1, 4.0, [0.1, 0.2], 100)
            self.assertGreaterEqual(d, 0.0)
            self.assertLessEqual(d, 1.0)

    def test_short_history_is_zero(self):
        self.assertEqual(deflated_sharpe(1.0, 1, 0.0, 3.0, [], 10), 0.0)

    def test_expected_max_sharpe_grows_with_trials(self):
        srs = [0.1, -0.1, 0.2]
        self.assertLess(expected_max_sharpe(srs, 10), expected_max_sharpe(srs, 100))

    def test_expected_max_sharpe_single_trial_is_zero(self):
        self.assertEqual(expected_max_sharpe([0.1], 1), 0.0)


def test_equity_summary_takes_r_atr_frac_pairs():
    # atr_frac=1.0 never clamps (5.0 * 1.0 > any sane fraction):
    # behavior must match the old float-list API exactly.
    eq = equity_summary([(1.0, 1.0), (-1.0, 1.0), (2.0, 1.0)], 0.01)
    assert eq.trade_count == 3
    expected = (1.01 * 0.99 * 1.02) - 1.0
    assert abs(eq.net_return - expected) < 1e-9


def test_leverage_clamp_caps_per_trade_fraction():
    # artifact shape: r=+50 with atr_frac=0.001 (a 5% price move against a
    # 0.1%-of-price stop). Old behavior: 0.02*50 = +100% per trade.
    # New: f_eff = min(0.02, 5.0*0.001) = 0.005 -> +25% per trade.
    eq = equity_summary([(50.0, 0.001)], 0.02)
    assert abs(eq.net_return - 0.25) < 1e-9


def test_leverage_clamp_inactive_for_wide_stops():
    # atr_frac=0.05 -> cap 0.25 > fraction 0.02: clamp is a no-op.
    eq = equity_summary([(2.0, 0.05)], 0.02)
    assert abs(eq.net_return - 0.04) < 1e-9


def test_max_leverage_constant():
    assert MAX_LEVERAGE == 5.0


if __name__ == "__main__":
    unittest.main()
