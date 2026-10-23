from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Bias = Literal["LONG", "SHORT", "NEUTRAL"]
Side = Literal["BUY", "SELL"]
Trend = Literal["BULLISH", "BEARISH", "NEUTRAL"]


@dataclass(frozen=True)
class Candle:
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_ccxt(cls, row: list[Any]) -> "Candle":
        if len(row) < 6:
            raise ValueError(f"Invalid OHLCV row: {row!r}")
        return cls(
            timestamp_ms=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )


@dataclass(frozen=True)
class ActionPlan:
    """Bracket-order description consumed by the trade simulator."""

    side: Side
    bias: Bias
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_percentage: float
    source_timeframe: str
    poi_kind: str | None = None
