"""Mechanism base: bar context precompute + [0,1] clip."""
import pytest

from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import (
    build_context,
    clip01,
)

from tests.helpers_v3 import uptrend

CFG = EngineConfigV3()


def test_clip01_bounds():
    assert clip01(-3.0) == 0.0
    assert clip01(0.5) == 0.5
    assert clip01(9.0) == 1.0


def test_build_context_populates_indicators_at_index():
    candles = uptrend(120)
    ctx = build_context(candles, len(candles) - 1, CFG)
    assert ctx.index == len(candles) - 1
    assert ctx.open == candles[-1].open
    assert ctx.high == candles[-1].high
    assert ctx.low == candles[-1].low
    assert ctx.close == candles[-1].close
    assert ctx.atr > 0.0
    assert ctx.donchian_high > 0.0
    assert ctx.band_up >= ctx.band_mid >= ctx.band_lo
    assert 0.0 <= ctx.rsi <= 100.0


def test_build_context_ignores_future_bars():
    candles = uptrend(120)
    early = build_context(candles, 100, CFG)
    sliced = build_context(candles[:101], 100, CFG)
    assert early.close == candles[100].close
    assert early.atr == sliced.atr
    assert early.adx == sliced.adx
    assert early.ema_fast == sliced.ema_fast
    assert early.ema_slow == sliced.ema_slow
    assert early.vol_ratio == sliced.vol_ratio
    assert early.donchian_high == sliced.donchian_high
    assert early.donchian_low == sliced.donchian_low
    assert early.band_mid == sliced.band_mid
    assert early.band_up == sliced.band_up
    assert early.band_lo == sliced.band_lo
    assert early.rsi == sliced.rsi
    assert early.roc == sliced.roc


def test_build_context_rejects_out_of_range_index():
    candles = uptrend(10)
    with pytest.raises(IndexError):
        build_context(candles, 10, CFG)
