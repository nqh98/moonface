# src/moonface/backtest/edge/regime_signals.py
"""Price-derived regime entry families. Same contract as
edge.signals: (candles, params) -> [(index, side)], causal by construction."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import fmean

from moonface.core.models import Candle

Entry = tuple[int, str]


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def _sma_at(closes: list[float], i: int, n: int) -> float | None:
    if i + 1 < n:
        return None
    return fmean(closes[i - n + 1:i + 1])


def vol_regime(candles: list[Candle], params: dict) -> list[Entry]:
    """Trend entries gated by the realized-vol regime. mode='low': trade trend
    only in the calmest tercile (rank < 1/3); mode='high': only in the loudest
    (rank > 2/3)."""
    window, mode, trend_n = params["window"], params["mode"], params["trend_n"]
    closes = _closes(candles)
    rets = [0.0] + [abs(math.log(closes[i] / closes[i - 1]))
                    for i in range(1, len(candles))]
    vols: list[float | None] = [None] * len(candles)
    for i in range(window, len(candles)):
        vols[i] = fmean(rets[i - window + 1:i + 1])
    out: list[Entry] = []
    for i in range(window * 2, len(candles)):
        recent = [v for v in vols[i - window + 1:i + 1] if v is not None]
        if len(recent) < window:
            continue
        rank = sum(1 for v in recent if v <= vols[i]) / len(recent)
        in_regime = rank < 1.0 / 3.0 if mode == "low" else rank > 2.0 / 3.0
        if not in_regime:
            continue
        sma = _sma_at(closes, i, trend_n)
        if sma is None or closes[i] == sma:
            continue
        out.append((i, "LONG" if closes[i] > sma else "SHORT"))
    return out


def seasonality(candles: list[Candle], params: dict) -> list[Entry]:
    """Calendar-conditioned trend entries: on the configured UTC weekdays
    and/or hours, enter in the direction of the `trend_n` SMA."""
    weekdays = set(params.get("weekdays", []))
    hours = set(params.get("hours", []))
    trend_n = params["trend_n"]
    closes = _closes(candles)
    out: list[Entry] = []
    for i, candle in enumerate(candles):
        ts = datetime.fromtimestamp(candle.timestamp_ms / 1000, tz=timezone.utc)
        if weekdays and ts.weekday() not in weekdays:
            continue
        if hours and ts.hour not in hours:
            continue
        if not weekdays and not hours:
            continue
        sma = _sma_at(closes, i, trend_n)
        if sma is None or closes[i] == sma:
            continue
        out.append((i, "LONG" if closes[i] > sma else "SHORT"))
    return out
