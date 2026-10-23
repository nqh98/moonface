"""REVERSION specialist: fade a rejected band stretch back to the mean."""
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import BarContext
from moonface.models.engine.v3.mechanisms.reversion import Reversion
from moonface.models.engine.v3.regime import DirState, Regime, VolState

CFG = EngineConfigV3()
M = Reversion()
RANGE = Regime(DirState.RANGING, VolState.NORMAL)


def _ctx(*, high, low, close, band_up, band_lo, mid=100.0, rsi=50.0):
    return BarContext(
        index=200, open=close, high=high, low=low, close=close,
        atr=1.0, adx=15.0, ema_fast=mid, ema_slow=mid, vol_ratio=1.0,
        donchian_high=high + 5, donchian_low=low - 5,
        band_mid=mid, band_up=band_up, band_lo=band_lo, rsi=rsi, roc=0.0)


def test_fades_upper_band_rejection_short():
    sig = M.evaluate(_ctx(high=106.0, low=101.0, close=102.0,
                          band_up=104.0, band_lo=96.0, rsi=78.0), RANGE)
    assert sig.direction == -1
    assert 0.0 <= sig.quality <= 1.0


def test_fades_lower_band_rejection_long():
    sig = M.evaluate(_ctx(high=99.0, low=94.0, close=98.0,
                          band_up=104.0, band_lo=96.0, rsi=22.0), RANGE)
    assert sig.direction == 1


def test_no_trigger_inside_bands():
    sig = M.evaluate(_ctx(high=101.0, low=99.0, close=100.0,
                          band_up=104.0, band_lo=96.0), RANGE)
    assert sig.direction == 0


def test_no_trigger_when_no_rejection():
    sig = M.evaluate(_ctx(high=106.0, low=104.5, close=105.5,
                          band_up=104.0, band_lo=96.0), RANGE)
    assert sig.direction == 0
