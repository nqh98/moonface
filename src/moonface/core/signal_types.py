from __future__ import annotations

from dataclasses import dataclass

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle


@dataclass(frozen=True)
class Signal:
    decision: str               # "LONG" | "SHORT" | "WAIT"
    price: float | None
    invalidation: float | None
    fraction: float | None
    reason: str
    kill_switch: bool = False   # participation advisor: realized-drawdown halt
    confidence: float = 0.0     # agreement strength [0,1]; NOT P(profit)
    timeframe: str = ""         # e.g. "4h"
    risk_notes: str = ""        # invalidation / sizing / caveat, human-readable
    tier: str = ""              # "" | "live" | "paper" | "participation" | "baseline"


def wait(reason: str) -> Signal:
    return Signal("WAIT", None, None, None, reason)


def sentinel_extended(bundle: DataBundle) -> DataBundle:
    """Generators stop one bar early because the backtest needs a fill bar
    after each signal. A sentinel copy of the last close lets the final closed
    bar be evaluated; entries at the sentinel index itself are discarded."""
    last = bundle.candles[-1]
    tf_ms = bundle.candles[1].timestamp_ms - bundle.candles[0].timestamp_ms
    sentinel = Candle(last.timestamp_ms + tf_ms, last.close, last.close,
                      last.close, last.close, 0.0)

    def ext(series):
        return None if series is None else list(series) + [None]

    return DataBundle(candles=list(bundle.candles) + [sentinel],
                      funding=ext(bundle.funding), basis=ext(bundle.basis),
                      feature=ext(bundle.feature))
