import math
import unittest

from moonface.research.matrix.baselines.metrics import baseline_metrics
from moonface.research.matrix.baselines.strategies import BaselineTrade


def _trade(net_return, day):
    ts = day * 86_400_000
    return BaselineTrade(
        side=1,
        entry_index=day,
        entry_ts_ms=ts,
        entry_px=100.0,
        exit_index=day,
        exit_ts_ms=ts + 3_600_000,
        exit_px=100.0 * (1 + net_return),
        net_return=net_return,
    )


class MetricsTest(unittest.TestCase):
    def test_ev_is_mean_net_return(self):
        m = baseline_metrics([_trade(0.02, 1), _trade(-0.01, 2), _trade(0.03, 3)])
        self.assertAlmostEqual(m.ev_per_trade, (0.02 - 0.01 + 0.03) / 3, places=8)

    def test_no_drawdown_gives_infinite_mar(self):
        m = baseline_metrics([_trade(0.01, 1), _trade(0.02, 2), _trade(0.01, 3)])
        self.assertEqual(m.max_drawdown, 0.0)
        self.assertTrue(math.isinf(m.mar))

    def test_es95_is_mean_worst_5pct_and_nonpositive(self):
        trades = [_trade(r / 100.0, i) for i, r in enumerate(range(-10, 10), 1)]
        m = baseline_metrics(trades)
        self.assertAlmostEqual(m.es95, -0.10, places=8)
        self.assertLessEqual(m.es95, 0.0)

    def test_drawdown_has_positive_duration(self):
        trades = [_trade(0.10, 1), _trade(-0.05, 2), _trade(-0.05, 3), _trade(0.20, 6)]
        m = baseline_metrics(trades)
        self.assertGreater(m.max_dd_duration_days, 0.0)
        self.assertLess(m.max_drawdown, 0.0)

    def test_empty_is_all_zero(self):
        m = baseline_metrics([])
        self.assertEqual(m.trade_count, 0)
        self.assertEqual(m.mar, 0.0)


if __name__ == "__main__":
    unittest.main()
