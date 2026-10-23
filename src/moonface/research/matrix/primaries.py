from __future__ import annotations

from dataclasses import dataclass, replace

from moonface.core.metrics import COST_FRACTION
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.edge.funding_signals import make_funding_fade
from moonface.research.trend_sim import TrendParams, simulate_donchian
from moonface.models.matrix.horizon import simulate_horizon

MATRIX_K = 2.0


@dataclass(frozen=True)
class MatrixTrade:
    primary: str
    entry_index: int
    exit_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    direction: int
    gross_r: float
    atr_frac: float
    mae_r: float
    state_tag: str

    @property
    def net_r_ungoverned(self) -> float:
        if self.atr_frac <= 0.0:
            return self.gross_r
        return self.gross_r - COST_FRACTION / self.atr_frac


def momentum_panel(
    candles: list[Candle], params: TrendParams, atr_period: int
) -> list[MatrixTrade]:
    fee_off = replace(params, fee_rate=0.0, slippage=0.0, funding_enabled=False)
    trades: list[MatrixTrade] = []
    for trade in simulate_donchian(candles, fee_off):
        entry = candles[trade.entry_index]
        atr_value = atr(candles[: trade.entry_index + 1], atr_period)
        atr_frac = atr_value / entry.close if entry.close > 0 else 0.0
        trades.append(
            MatrixTrade(
                primary="momentum_breakout",
                entry_index=trade.entry_index,
                exit_index=trade.exit_index,
                entry_ts_ms=entry.timestamp_ms,
                exit_ts_ms=candles[trade.exit_index].timestamp_ms,
                direction=1 if trade.side == "BUY" else -1,
                gross_r=trade.r_multiple,
                atr_frac=atr_frac,
                mae_r=trade.mae_r,
                state_tag="UP/native",
            )
        )
    return trades


def funding_panel(
    candles: list[Candle],
    funding: list[float | None],
    window: int,
    z_thr: float,
    horizon: int,
    k: float,
    atr_period: int,
) -> list[MatrixTrade]:
    entries = make_funding_fade(funding)(candles, {"window": window, "z_thr": z_thr})
    trades: list[MatrixTrade] = []
    last_exit_index = -1
    for entry_index, side in entries:
        if entry_index <= last_exit_index:
            continue
        direction = 1 if side == "LONG" else -1
        trade = simulate_horizon(candles, entry_index, direction, horizon, k, atr_period)
        if trade is None:
            continue
        trades.append(
            MatrixTrade(
                primary="funding_fade",
                entry_index=trade.entry_index,
                exit_index=trade.exit_index,
                entry_ts_ms=trade.entry_ts_ms,
                exit_ts_ms=trade.exit_ts_ms,
                direction=trade.direction,
                gross_r=trade.gross_r,
                atr_frac=trade.atr_frac,
                mae_r=trade.mae_r,
                state_tag=f"z{z_thr}",
            )
        )
        last_exit_index = trade.exit_index
    return trades
