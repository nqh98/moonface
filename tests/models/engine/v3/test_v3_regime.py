"""Regime classifier: trend/range x volatility, conservative RANGING default."""
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.regime import (
    DirState,
    VolState,
    classify_dir,
    classify_regime,
    classify_vol,
)

from tests.helpers_v3 import c, downtrend, flat_range, uptrend

CFG = EngineConfigV3()


def test_dir_state_up_down_range():
    assert classify_dir(uptrend(80), CFG) == DirState.TRENDING_UP
    assert classify_dir(downtrend(80), CFG) == DirState.TRENDING_DOWN
    assert classify_dir(flat_range(80), CFG) == DirState.RANGING


def test_vol_state_extreme_from_recent_spike():
    quiet = uptrend(120, step=0.2, wick=0.05)
    spiked = quiet + [c(120 + j, 200.0, 260.0, 195.0, 255.0) for j in range(3)]
    assert classify_vol(spiked, CFG) == VolState.EXTREME


def test_vol_state_normal_for_steady_series():
    assert classify_vol(uptrend(120), CFG) == VolState.NORMAL


def test_classify_regime_pairs_both_axes():
    reg = classify_regime(uptrend(80), CFG)
    assert reg.dir_state == DirState.TRENDING_UP
    assert reg.vol_state in (VolState.QUIET, VolState.NORMAL, VolState.HIGH)
