# src/moonface/signal/engine/regime.py
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.indicators import sma
from moonface.core.models import Candle
from moonface.models.baseline import vol_ratio
from moonface.models.engine.config import EngineConfig


@dataclass(frozen=True)
class Regime:
    trend: int        # -1, 0, +1
    vol_state: str    # "normal" | "high" | "extreme"


def _vol_state(candles: list[Candle], cfg: EngineConfig) -> str:
    ratio = vol_ratio(candles, cfg.vol_window)
    if ratio is None:
        return "normal"
    if ratio >= cfg.extreme_vol_ratio:
        return "extreme"
    if ratio >= cfg.high_vol_ratio:
        return "high"
    return "normal"


def classify_regime(candles_4h: list[Candle], cfg: EngineConfig) -> Regime:
    closes = [c.close for c in candles_4h]
    if len(closes) < cfg.regime_ma_slow:
        return Regime(trend=0, vol_state=_vol_state(candles_4h, cfg))
    ma_fast = sma(closes, cfg.regime_ma_fast)
    ma_slow = sma(closes, cfg.regime_ma_slow)
    close = closes[-1]
    if close > ma_slow and ma_fast > ma_slow:
        trend = 1
    elif close < ma_slow and ma_fast < ma_slow:
        trend = -1
    else:
        trend = 0
    return Regime(trend=trend, vol_state=_vol_state(candles_4h, cfg))
