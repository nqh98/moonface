"""PULLBACK specialist: reclaim of the fast EMA in an established trend."""
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import BarContext
from moonface.models.engine.v3.mechanisms.pullback import Pullback
from moonface.models.engine.v3.regime import DirState, Regime, VolState

CFG = EngineConfigV3()
M = Pullback()
UP = Regime(DirState.TRENDING_UP, VolState.QUIET)
RANGE = Regime(DirState.RANGING, VolState.QUIET)


def _ctx(*, open_, high, low, close, ema_fast, adx=30.0):
    return BarContext(
        index=200, open=open_, high=high, low=low, close=close,
        atr=1.0, adx=adx, ema_fast=ema_fast, ema_slow=ema_fast - 5.0,
        vol_ratio=1.0, donchian_high=high + 5, donchian_low=low - 5,
        band_mid=close, band_up=close + 2, band_lo=close - 2,
        rsi=55.0, roc=0.01)


def test_fires_long_on_ema_tag_and_reclaim():
    sig = M.evaluate(_ctx(open_=100.5, high=102.0, low=99.9, close=101.5,
                          ema_fast=100.0), UP)
    assert sig.direction == 1
    assert 0.0 <= sig.quality <= 1.0


def test_no_trigger_when_price_never_tags_ema():
    sig = M.evaluate(_ctx(open_=110.0, high=112.0, low=108.0, close=111.0,
                          ema_fast=100.0), UP)
    assert sig.direction == 0


def test_no_trigger_when_not_reclaimed():
    sig = M.evaluate(_ctx(open_=101.0, high=101.2, low=98.0, close=99.0,
                          ema_fast=100.0), UP)
    assert sig.direction == 0


def test_range_regime_gives_no_direction():
    sig = M.evaluate(_ctx(open_=100.5, high=102.0, low=99.9, close=101.5,
                          ema_fast=100.0), RANGE)
    assert sig.direction == 0
