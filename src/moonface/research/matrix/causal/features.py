"""Causal price, vol, and funding features for the matrix research lane."""
from __future__ import annotations

from statistics import fmean, pstdev

from moonface.core.models import Candle
from moonface.core.risk import atr

VOL_LOOKBACK = 100
DONCHIAN_N = 20
ATR_PERIOD = 14
FUNDING_WINDOW = 60
WARMUP = VOL_LOOKBACK

FEATURE_NAMES: tuple[str, ...] = (
    "realized_vol",
    "donchian_pos",
    "atr_norm_range",
    "funding_z",
)
# Proxy slots from source-spec section 3 are intentionally UNIMPLEMENTED here
# (data not-ready / falsified): options_gamma_proxy, institutional_flow_proxy,
# liquidation_cluster_proxy. They plug in behind extract() in a later step.


def _realized_vol(candles: list[Candle], i: int) -> float:
    if i < VOL_LOOKBACK or i >= len(candles):
        return 0.0
    window = candles[i - VOL_LOOKBACK:i + 1]
    closes = [c.close for c in window]
    rets = []
    for j in range(1, len(closes)):
        prev = closes[j - 1]
        cur = closes[j]
        if prev > 0:
            rets.append(cur / prev - 1.0)
    if len(rets) < 2:
        return 0.0
    return float(pstdev(rets))


def _donchian_pos(candles: list[Candle], i: int) -> float:
    if i - DONCHIAN_N + 1 < 0 or i >= len(candles):
        return 0.5
    window = candles[i - DONCHIAN_N + 1:i + 1]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    if hi <= lo:
        return 0.5
    return (candles[i].close - lo) / (hi - lo)


def _atr_norm_range(candles: list[Candle], i: int) -> float:
    if i < ATR_PERIOD - 1 or i >= len(candles):
        return 0.0
    a = atr(candles[:i + 1], ATR_PERIOD)
    if a <= 0:
        return 0.0
    # Proxy slot for the live range lane: compare the closed bar to its own ATR.
    return (candles[i].high - candles[i].low) / a


def _funding_z(funding: list[float | None], i: int) -> float:
    if i < FUNDING_WINDOW - 1 or i >= len(funding):
        return 0.0
    recent = funding[i + 1 - FUNDING_WINDOW:i + 1]
    if any(v is None for v in recent):
        return 0.0
    mu = fmean(recent)
    sd = pstdev(recent)
    if sd <= 0:
        return 0.0
    return float((recent[-1] - mu) / sd)


class CausalFeatureExtractor:
    warmup: int = WARMUP

    def extract(
        self,
        candles: list[Candle],
        funding: list[float | None],
        i: int,
    ) -> list[float]:
        if i < self.warmup or i >= len(candles):
            return [0.0] * len(FEATURE_NAMES)
        return [
            _realized_vol(candles, i),
            _donchian_pos(candles, i),
            _atr_norm_range(candles, i),
            _funding_z(funding, i),
        ]


__all__ = [
    "ATR_PERIOD",
    "CausalFeatureExtractor",
    "DONCHIAN_N",
    "FEATURE_NAMES",
    "FUNDING_WINDOW",
    "VOL_LOOKBACK",
    "WARMUP",
]
