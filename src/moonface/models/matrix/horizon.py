from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.risk import atr, horizon_r, risk_unit


@dataclass(frozen=True)
class HorizonTrade:
    entry_index: int
    exit_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    direction: int
    gross_r: float
    mae_r: float
    atr_frac: float


def simulate_horizon(candles: list[Candle], entry_index: int, direction: int,
                     horizon_bars: int, k: float, atr_period: int
                     ) -> HorizonTrade | None:
    risk = risk_unit(candles, entry_index, k, atr_period)
    if risk is None:
        return None

    entry = candles[entry_index]
    atr_value = atr(candles[: entry_index + 1], atr_period)
    atr_frac = atr_value / entry.close if entry.close > 0 else 0.0
    if atr_frac <= 0:
        return None

    side = "LONG" if direction > 0 else "SHORT"
    gross_r = horizon_r(entry_index, side, candles, k, atr_period, horizon_bars)
    if gross_r is None:
        return None

    exit_index = min(entry_index + horizon_bars, len(candles) - 1)
    mae_r = 0.0
    for j in range(entry_index + 1, exit_index + 1):
        bar = candles[j]
        if direction > 0:
            excursion = (bar.low - entry.close) / risk
        else:
            excursion = (entry.close - bar.high) / risk
        mae_r = min(mae_r, excursion)

    return HorizonTrade(
        entry_index=entry_index,
        exit_index=exit_index,
        entry_ts_ms=entry.timestamp_ms,
        exit_ts_ms=candles[exit_index].timestamp_ms,
        direction=direction,
        gross_r=gross_r,
        mae_r=round(mae_r, 4),
        atr_frac=atr_frac,
    )
