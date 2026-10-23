# tests/test_trend_sim_revalidation.py
import unittest

from moonface.core.models import Candle
from moonface.research.trend_sim import TrendParams, simulate_donchian


def _fixture():
    """120-bar deterministic zigzag: 8-bar +3% runs then 4-bar -5% spikes.
    Forces breakout entries, trailing stop-outs, and re-entries."""
    cs = []
    price = 100.0
    for k in range(120):
        price *= 1.03 if (k % 12) < 8 else 0.95
        cs.append(Candle(
            timestamp_ms=1_000_000 + k * 14_400_000,
            open=round(price / 1.01, 4), high=round(price * 1.015, 4),
            low=round(price * 0.97, 4), close=round(price, 4), volume=10.0))
    return cs


# Golden output of the CURRENT simulator (captured 2026-06-20). exit_mode="trail"
# default MUST reproduce these exactly. (side, entry_idx, entry, exit_idx, exit,
# r_multiple, mae_r, hold_bars, funding_paid_r)
_GOLDEN_TRAIL = [
    ("BUY", 31, 134.92713, 33, 121.436865, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 43, 139.216774, 45, 125.29762, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 55, 143.642786, 57, 129.281099, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 67, 148.209468, 69, 133.391185, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 79, 152.921423, 81, 137.632035, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 91, 157.783052, 93, 142.007589, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 103, 162.799359, 105, 146.522288, -1.0182, 1.2573, 2, 0.0),
    ("BUY", 115, 167.975046, 117, 151.180543, -1.0182, 1.2573, 2, 0.0),
]

_BASE = dict(entry_n=20, trail_n=10, atr_period=14, k_stop=2.0, long_only=True,
             fee_rate=0.00045, slippage=0.0005, funding_enabled=False)


class TrendSimIdentity(unittest.TestCase):
    def test_default_trail_matches_golden(self):
        ts = simulate_donchian(_fixture(), TrendParams(**_BASE), None)
        got = [(t.side, t.entry_index, t.entry, t.exit_index, t.exit,
                t.r_multiple, t.mae_r, t.hold_bars, t.funding_paid_r) for t in ts]
        self.assertEqual(got, _GOLDEN_TRAIL)

    def test_explicit_trail_equals_default(self):
        cs = _fixture()
        a = simulate_donchian(cs, TrendParams(**_BASE), None)
        b = simulate_donchian(cs, TrendParams(exit_mode="trail", **_BASE), None)
        self.assertEqual([t.r_multiple for t in a], [t.r_multiple for t in b])


class TrendSimExitModes(unittest.TestCase):
    def test_fixed_horizon_caps_hold_bars(self):
        cs = _fixture()
        p = TrendParams(exit_mode="fixed_horizon", fh_bars=3, **_BASE)
        ts = simulate_donchian(cs, p, None)
        self.assertTrue(ts)
        # no trade held longer than fh_bars (time exit), stops may exit earlier
        self.assertTrue(all(t.hold_bars <= 3 for t in ts))

    def test_stop_only_never_trails_up(self):
        # stop_only keeps the initial ATR stop; on a clean uptrend it should hold
        # to the end (one trade), unlike trail which ratchets and can exit earlier.
        cs = []
        price = 100.0
        for k in range(60):
            price *= 1.02
            cs.append(Candle(timestamp_ms=1_000_000 + k * 14_400_000,
                             open=round(price / 1.005, 4), high=round(price * 1.01, 4),
                             low=round(price * 0.995, 4), close=round(price, 4), volume=10.0))
        p = TrendParams(exit_mode="stop_only", entry_n=20, trail_n=10, atr_period=14,
                        k_stop=2.0, long_only=True, fee_rate=0.0, slippage=0.0,
                        funding_enabled=False)
        ts = simulate_donchian(cs, p, None)
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].exit_index, len(cs) - 1)

    def test_stop_extra_slip_worsens_stop_exit_r(self):
        cs = _fixture()
        base = TrendParams(**_BASE)
        slipped = TrendParams(stop_extra_slip=0.01, **_BASE)
        rb = sum(t.r_multiple for t in simulate_donchian(cs, base, None))
        rs = sum(t.r_multiple for t in simulate_donchian(cs, slipped, None))
        self.assertLess(rs, rb)

    def test_next_bar_open_changes_fills(self):
        cs = _fixture()
        base = TrendParams(**_BASE)
        nbo = TrendParams(next_bar_open=True, **_BASE)
        a = [t.entry for t in simulate_donchian(cs, base, None)]
        b = [t.entry for t in simulate_donchian(cs, nbo, None)]
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
