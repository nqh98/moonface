from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.indicators import (
    adx,
    donchian_high,
    donchian_low,
    ema,
    roc,
    rsi,
    sma,
    stdev,
)
from moonface.models.engine.v3.regime import Regime


def clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


@dataclass(frozen=True)
class MechanismSignal:
    direction: int
    quality: float
    detail: str


@dataclass(frozen=True)
class BarContext:
    index: int
    open: float
    high: float
    low: float
    close: float
    atr: float
    adx: float
    ema_fast: float
    ema_slow: float
    vol_ratio: float
    donchian_high: float
    donchian_low: float
    band_mid: float
    band_up: float
    band_lo: float
    rsi: float
    roc: float


class Mechanism(Protocol):
    name: str

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        ...


def build_context(candles: list[Candle], index: int, cfg: EngineConfigV3) -> BarContext:
    """Precompute shared indicators from candles[:index+1] only."""
    if index < 0 or index >= len(candles):
        raise IndexError(index)

    window = candles[: index + 1]
    closes = [candle.close for candle in window]
    bar = window[-1]

    atr_value = atr(window, cfg.atr_period)
    baseline_atr = atr(window, cfg.vol_baseline)
    band_mid = sma(closes, cfg.band_period)
    band_spread = stdev(closes, cfg.band_period)

    return BarContext(
        index=index,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        atr=atr_value,
        adx=adx(window, cfg.adx_period),
        ema_fast=ema(closes, cfg.ema_fast),
        ema_slow=ema(closes, cfg.ema_slow),
        vol_ratio=(atr_value / baseline_atr) if baseline_atr > 0.0 else 0.0,
        donchian_high=donchian_high(window, cfg.breakout_n),
        donchian_low=donchian_low(window, cfg.breakout_n),
        band_mid=band_mid,
        band_up=band_mid + (cfg.band_k * band_spread),
        band_lo=band_mid - (cfg.band_k * band_spread),
        rsi=rsi(closes, cfg.rsi_period),
        roc=roc(closes, cfg.roc_n),
    )


__all__ = [
    "BarContext",
    "Mechanism",
    "MechanismSignal",
    "build_context",
    "clip01",
]
