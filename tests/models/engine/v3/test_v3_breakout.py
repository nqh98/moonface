"""BREAKOUT specialist: channel break in the regime trend direction."""
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import BarContext, build_context
from moonface.models.engine.v3.mechanisms.breakout import Breakout
from moonface.models.engine.v3.regime import DirState, Regime, VolState

from tests.helpers_v3 import downtrend, flat_range, uptrend

CFG = EngineConfigV3()
M = Breakout()
UP = Regime(DirState.TRENDING_UP, VolState.NORMAL)
DOWN = Regime(DirState.TRENDING_DOWN, VolState.NORMAL)


def test_fires_long_on_fresh_high_in_uptrend():
    candles = uptrend(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction == 1
    assert 0.0 <= sig.quality <= 1.0


def test_no_trigger_without_breakout():
    candles = flat_range(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction == 0


def test_long_regime_never_fires_short():
    candles = uptrend(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction in (0, 1)


def test_fires_short_on_fresh_low_in_downtrend():
    candles = downtrend(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), DOWN)
    assert sig.direction == -1
    assert 0.0 <= sig.quality <= 1.0


def test_no_trigger_on_equal_edge_or_zero_atr():
    equal_edge = BarContext(
        index=1,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        atr=1.0,
        adx=30.0,
        ema_fast=100.0,
        ema_slow=99.0,
        vol_ratio=1.0,
        donchian_high=100.0,
        donchian_low=98.0,
        band_mid=100.0,
        band_up=101.0,
        band_lo=99.0,
        rsi=55.0,
        roc=0.1,
    )
    zero_atr = BarContext(
        index=1,
        open=100.0,
        high=101.0,
        low=99.0,
        close=101.0,
        atr=0.0,
        adx=30.0,
        ema_fast=100.0,
        ema_slow=99.0,
        vol_ratio=0.0,
        donchian_high=100.0,
        donchian_low=98.0,
        band_mid=100.0,
        band_up=101.0,
        band_lo=99.0,
        rsi=55.0,
        roc=0.1,
    )
    assert M.evaluate(equal_edge, UP).direction == 0
    assert M.evaluate(zero_atr, UP).direction == 0


def test_invalid_scales_stay_flat():
    bad = Breakout(EngineConfigV3(ext_scale=0.0, roc_scale=-1.0))
    candles = uptrend(60)
    sig = bad.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction == 0
    assert sig.quality == 0.0


def test_quality_rises_with_stronger_thrust():
    weak = uptrend(60, step=0.3)
    strong = uptrend(60, step=3.0)
    qw = M.evaluate(build_context(weak, len(weak) - 1, CFG), UP).quality
    qs = M.evaluate(build_context(strong, len(strong) - 1, CFG), UP).quality
    assert qs >= qw
