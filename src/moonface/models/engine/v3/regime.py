from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from moonface.core.models import Candle
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.indicators import adx, ema, vol_ratio


class DirState(Enum):
    TRENDING_UP = "TRENDING_UP"
    RANGING = "RANGING"
    TRENDING_DOWN = "TRENDING_DOWN"


class VolState(Enum):
    QUIET = "QUIET"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass(frozen=True)
class Regime:
    dir_state: DirState
    vol_state: VolState


def classify_dir(candles: list[Candle], cfg: EngineConfigV3) -> DirState:
    """Return a directional regime only when ADX confirms a trend."""
    if adx(candles, cfg.adx_period) < cfg.adx_trend:
        return DirState.RANGING

    closes = [candle.close for candle in candles]
    fast = ema(closes, cfg.ema_fast)
    slow = ema(closes, cfg.ema_slow)

    if fast > slow:
        return DirState.TRENDING_UP
    if fast < slow:
        return DirState.TRENDING_DOWN
    return DirState.RANGING


def classify_vol(candles: list[Candle], cfg: EngineConfigV3) -> VolState:
    ratio = vol_ratio(candles, cfg.atr_period, cfg.vol_baseline)
    if ratio >= cfg.vol_extreme_ratio:
        return VolState.EXTREME
    if ratio >= cfg.vol_high_ratio:
        return VolState.HIGH
    if ratio < cfg.vol_quiet_ratio:
        return VolState.QUIET
    return VolState.NORMAL


def classify_regime(candles: list[Candle], cfg: EngineConfigV3) -> Regime:
    return Regime(
        dir_state=classify_dir(candles, cfg),
        vol_state=classify_vol(candles, cfg),
    )
