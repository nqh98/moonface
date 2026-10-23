import unittest

from moonface.core.models import Candle
from moonface.models.matrix.horizon import HorizonTrade, simulate_horizon


def _bar(ts: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(timestamp_ms=ts, open=open_, high=high, low=low, close=close, volume=1.0)


def _series(rows: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [_bar(1_000 * i, o, h, l, c) for i, (o, h, l, c) in enumerate(rows)]


class TestSimulateHorizon(unittest.TestCase):
    def test_long_trade_records_horizon_exit_and_gross_r(self) -> None:
        candles = _series(
            [(100.0, 100.0, 100.0, 100.0)] * 13
            + [(100.0, 102.0, 98.0, 100.0)]
            + [(100.0, 100.0, 100.0, 100.0),
               (100.0, 100.0, 100.0, 100.0),
               (100.0, 101.0, 96.0, 100.0),
               (100.0, 103.0, 101.0, 103.0)]
        )

        trade = simulate_horizon(candles, entry_index=15, direction=1, horizon_bars=2,
                                 k=2.0, atr_period=14)

        self.assertIsInstance(trade, HorizonTrade)
        assert trade is not None
        self.assertEqual(trade.entry_index, 15)
        self.assertEqual(trade.exit_index, 17)
        self.assertEqual(trade.direction, 1)
        self.assertGreater(trade.gross_r, 0.0)

    def test_exit_index_clamps_to_last_bar(self) -> None:
        candles = _series(
            [(100.0, 100.0, 100.0, 100.0)] * 13
            + [(100.0, 102.0, 98.0, 100.0)]
            + [(100.0, 100.0, 100.0, 100.0),
               (100.0, 100.0, 100.0, 100.0),
               (100.0, 101.0, 96.0, 100.0),
               (100.0, 103.0, 101.0, 103.0)]
        )

        trade = simulate_horizon(candles, entry_index=15, direction=1, horizon_bars=99,
                                 k=2.0, atr_period=14)

        self.assertIsInstance(trade, HorizonTrade)
        assert trade is not None
        self.assertEqual(trade.exit_index, len(candles) - 1)
        self.assertEqual(trade.exit_ts_ms, candles[-1].timestamp_ms)

    def test_mae_r_tracks_worst_adverse_excursion(self) -> None:
        candles = _series(
            [(100.0, 100.0, 100.0, 100.0)] * 13
            + [(100.0, 102.0, 98.0, 100.0)]
            + [(100.0, 100.0, 100.0, 100.0),
               (100.0, 100.0, 100.0, 100.0),
               (100.0, 101.0, 94.0, 100.0),
               (100.0, 103.0, 101.0, 103.0)]
        )

        trade = simulate_horizon(candles, entry_index=15, direction=1, horizon_bars=2,
                                 k=2.0, atr_period=14)

        self.assertIsInstance(trade, HorizonTrade)
        assert trade is not None
        self.assertLess(trade.mae_r, 0.0)

    def test_returns_none_when_risk_or_atr_frac_is_undefined(self) -> None:
        candles = _series([(100.0, 100.0, 100.0, 100.0)] * 5)

        trade = simulate_horizon(candles, entry_index=3, direction=1, horizon_bars=2,
                                 k=2.0, atr_period=14)

        self.assertIsNone(trade)

    def test_future_beyond_horizon_does_not_change_result(self) -> None:
        candles = _series(
            [(100.0, 100.0, 100.0, 100.0)] * 13
            + [(100.0, 102.0, 98.0, 100.0)]
            + [(100.0, 100.0, 100.0, 100.0),
               (100.0, 100.0, 100.0, 100.0),
               (100.0, 101.0, 96.0, 100.0),
               (100.0, 103.0, 101.0, 103.0)]
        )
        extended = candles + [_bar(99_000, 999.0, 999.0, 999.0, 999.0)]

        left = simulate_horizon(candles, entry_index=15, direction=1, horizon_bars=2,
                                k=2.0, atr_period=14)
        right = simulate_horizon(extended, entry_index=15, direction=1, horizon_bars=2,
                                 k=2.0, atr_period=14)

        self.assertIsInstance(left, HorizonTrade)
        self.assertIsInstance(right, HorizonTrade)
        assert left is not None and right is not None
        self.assertEqual(left.gross_r, right.gross_r)
        self.assertEqual(left.mae_r, right.mae_r)
