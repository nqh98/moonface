from dataclasses import FrozenInstanceError, fields

import unittest

from moonface.core.metrics import COST_FRACTION
from moonface.core.models import Candle
from moonface.research.trend_sim import TrendParams
from moonface.research.matrix.primaries import (
    MATRIX_K,
    MatrixTrade,
    funding_panel,
    momentum_panel,
)


def _bar(ts: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(timestamp_ms=ts, open=open_, high=high, low=low, close=close, volume=1.0)


def _flat_candles(n: int, price: float = 100.0) -> list[Candle]:
    return [_bar(i * 1_000, price, price + 1.0, price - 1.0, price) for i in range(n)]


def _trending_up_candles(bars: int = 40) -> list[Candle]:
    out: list[Candle] = []
    for i in range(bars):
        p = 100.0 + i * 3.0
        out.append(_bar(i * 1_000, p, p + 1.0, p - 1.0, p))
    return out


class TestMatrixTrade(unittest.TestCase):
    def test_shape_is_frozen_and_net_r_ungoverned_subtracts_one_cost(self) -> None:
        assert [field.name for field in fields(MatrixTrade)] == [
            "primary",
            "entry_index",
            "exit_index",
            "entry_ts_ms",
            "exit_ts_ms",
            "direction",
            "gross_r",
            "atr_frac",
            "mae_r",
            "state_tag",
        ]

        trade = MatrixTrade(
            primary="momentum_breakout",
            entry_index=1,
            exit_index=3,
            entry_ts_ms=100,
            exit_ts_ms=300,
            direction=1,
            gross_r=2.5,
            atr_frac=0.005,
            mae_r=-0.4,
            state_tag="UP/native",
        )

        with self.assertRaises(FrozenInstanceError):
            trade.primary = "x"

        self.assertLess(trade.net_r_ungoverned, trade.gross_r)
        self.assertAlmostEqual(trade.net_r_ungoverned, 2.5 - COST_FRACTION / 0.005)


class TestPrimaries(unittest.TestCase):
    def test_momentum_panel_produces_long_trades_on_uptrend(self) -> None:
        candles = _trending_up_candles()
        params = TrendParams(
            entry_n=5,
            trail_n=3,
            atr_period=14,
            k_stop=2.0,
            long_only=True,
            fee_rate=0.00045,
            slippage=0.0005,
        )

        trades = momentum_panel(candles, params, atr_period=14)

        self.assertGreaterEqual(len(trades), 1)
        self.assertTrue(all(trade.primary == "momentum_breakout" for trade in trades))
        self.assertTrue(all(trade.direction == 1 for trade in trades))
        self.assertTrue(all(trade.atr_frac > 0.0 for trade in trades))
        self.assertEqual([trade.entry_index for trade in trades], sorted(t.entry_index for t in trades))
        for prev, cur in zip(trades, trades[1:]):
            self.assertGreaterEqual(cur.entry_index, prev.exit_index)

    def test_funding_panel_produces_non_overlapping_shorts(self) -> None:
        candles = _flat_candles(12)
        funding = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 5.5, 5.75, 6.0, 6.25, 6.5, 6.75]

        trades = funding_panel(
            candles,
            funding=funding,
            window=3,
            z_thr=1.0,
            horizon=2,
            k=MATRIX_K,
            atr_period=2,
        )

        self.assertGreaterEqual(len(trades), 1)
        self.assertTrue(all(trade.primary == "funding_fade" for trade in trades))
        self.assertTrue(any(trade.direction == -1 for trade in trades))
        self.assertTrue(all(trade.state_tag == "z1.0" for trade in trades))
        self.assertTrue(all(trade.atr_frac > 0.0 for trade in trades))
        self.assertEqual([trade.entry_index for trade in trades], sorted(t.entry_index for t in trades))
        for prev, cur in zip(trades, trades[1:]):
            self.assertGreater(cur.entry_index, prev.exit_index)
