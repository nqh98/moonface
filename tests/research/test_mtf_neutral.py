import math
import unittest

from moonface.core.models import Candle
from moonface.research.mtf.grid import broaden_best_cell
from moonface.research.mtf.neutral import (DAILY_MS, beta_lookup_for,
                                           daily_returns, hedged_leg,
                                           rolling_daily_betas)


def _c15(close: float, i: int) -> Candle:
    # 15m base series (matches the MTF cells); wick gives ATR a nonzero range
    return Candle(timestamp_ms=i * 900_000, open=close, high=close + 1.5,
                  low=close - 1.5, close=close, volume=1.0)


def _daily_candles(closes: list[float]) -> list[Candle]:
    # one bar per distinct UTC day so daily_returns() yields one return per pair
    return [Candle(timestamp_ms=k * DAILY_MS, open=c, high=c + 1, low=c - 1,
                   close=c, volume=1.0) for k, c in enumerate(closes)]


def _osc_series(n: int) -> list[Candle]:
    # uptrend + oscillation so the 4h trend_strength gate fires AND the 15m RSI
    # counter-trend entry finds dips/rips -> a nonempty trade set
    return [_c15(100.0 + 0.05 * i + 8.0 * math.sin(i / 50.0), i) for i in range(n)]


class Beta0AnchorTest(unittest.TestCase):
    def test_beta0_reproduces_raw_bit_for_bit(self):
        candles = _osc_series(8000)
        res = hedged_leg(candles, candles, broaden_best_cell(), beta=0.0)
        self.assertGreater(len(res["raw"]), 0, "gate must fire for a real anchor")
        self.assertEqual(len(res["raw"]), len(res["hedged"]))
        for raw, hed in zip(res["raw"], res["hedged"]):
            self.assertEqual(raw["i"], hed["i"])
            self.assertEqual(raw["side"], hed["side"])
            # no rounding anywhere on the beta=0 path -> exact equality
            self.assertEqual(raw["net_r"], hed["net_r"])

    def test_unit_beta_moves_the_pnl_when_market_moves_in_the_hold(self):
        # asset == market, so a unit hedge subtracts the asset's own move over the
        # hold -> hedged must differ from raw for at least one trade
        candles = _osc_series(8000)
        res = hedged_leg(candles, candles, broaden_best_cell(), beta=1.0)
        self.assertGreater(len(res["hedged"]), 0)
        diffs = [h["net_r"] - r["net_r"]
                 for r, h in zip(res["raw"], res["hedged"])]
        self.assertTrue(any(abs(d) > 1e-9 for d in diffs))


class DailyReturnsTest(unittest.TestCase):
    def test_one_close_per_day_close_to_close(self):
        rets = daily_returns(_daily_candles([100.0, 110.0, 121.0]))
        self.assertEqual(len(rets), 2)
        self.assertAlmostEqual(rets[0][1], 0.10)
        self.assertAlmostEqual(rets[1][1], 0.10)
        self.assertEqual(rets[0][0], 1 * DAILY_MS)   # keyed by the later day's ts


class RollingBetaTest(unittest.TestCase):
    def _linear_pair(self, mkt_rets, k):
        # asset return = k * market return exactly -> population beta == k
        mkt = [100.0]
        ast = [100.0]
        for r in mkt_rets:
            mkt.append(mkt[-1] * (1 + r))
            ast.append(ast[-1] * (1 + k * r))
        return _daily_candles(ast), _daily_candles(mkt)

    def test_recovers_the_true_beta_after_warmup(self):
        rets = [0.02, -0.01, 0.03, -0.02, 0.015, -0.005, 0.01, -0.02, 0.025]
        asset, market = self._linear_pair(rets, k=2.0)
        betas = rolling_daily_betas(asset, market, window=10, min_days=3)
        # last estimate has enough obs and should equal the linear slope 2.0
        self.assertAlmostEqual(betas[-1][1], 2.0, places=6)

    def test_warmup_falls_back_to_unit_beta(self):
        rets = [0.02, -0.01, 0.03, -0.02, 0.01]
        asset, market = self._linear_pair(rets, k=2.0)
        betas = rolling_daily_betas(asset, market, window=10, min_days=4)
        # first (min_days) estimates lack enough prior obs -> unit hedge
        self.assertEqual(betas[0][1], 1.0)
        self.assertEqual(betas[3][1], 1.0)

    def test_no_look_ahead_appending_a_later_day_leaves_earlier_betas_unchanged(self):
        rets = [0.02, -0.01, 0.03, -0.02, 0.015, -0.005, 0.01]
        asset, market = self._linear_pair(rets, k=2.0)
        base = rolling_daily_betas(asset, market, window=20, min_days=3)
        # extend BOTH series by one genuinely-later day with a violent joint move;
        # it must add a new final beta but recompute none of the earlier ones
        d = len(asset)
        shock = Candle(timestamp_ms=d * DAILY_MS, open=1.0, high=1.0, low=1.0,
                       close=1.0, volume=1.0)
        shocked = rolling_daily_betas(asset + [shock], market + [shock],
                                      window=20, min_days=3)
        self.assertEqual(len(shocked), len(base) + 1)
        for (ts_a, b_a), (ts_b, b_b) in zip(base, shocked[:len(base)]):
            self.assertEqual(ts_a, ts_b)
            self.assertAlmostEqual(b_a, b_b, places=9)


class BetaLookupTest(unittest.TestCase):
    def test_entry_uses_most_recent_prior_daily_beta(self):
        candles = _osc_series(4000)
        entries = [(2000, "LONG"), (3000, "SHORT")]
        lut = beta_lookup_for(entries, candles, candles)
        for i, _ in entries:
            self.assertIn(candles[i].timestamp_ms, lut)
            self.assertIsInstance(lut[candles[i].timestamp_ms], float)


if __name__ == "__main__":
    unittest.main()
