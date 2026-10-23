# tests/research/practical/test_exits_scaled.py
import pytest

from moonface.core.exits import EXECUTABLE_EXITS
from moonface.research.practical import exits_scaled as ex


def test_timeframes_and_hold_table():
    assert ex.TIMEFRAMES == ["1h", "4h"]
    assert ex.TF_MAX_HOLD_BARS["1h"] == [24, 48, 96]
    assert ex.TF_MAX_HOLD_BARS["4h"] == [30, 60, 120]


def test_mean_reversion_maps_to_reclaim_exit_and_scales_hold():
    name, param_sets = ex.exit_for("4h", "reversion_in_range")
    assert name == "mean_revert_reclaim"
    assert name in EXECUTABLE_EXITS
    holds = {p["max_bars"] for p in param_sets}
    assert holds == {30, 60, 120}          # 4h band
    assert all(p["ref"] in ("ema", "range_mid") for p in param_sets)
    assert all(p["atr_period"] == 14 for p in param_sets)


def test_trend_maps_to_atr_trail_and_scales_hold():
    name, param_sets = ex.exit_for("1h", "atr_channel_break")
    assert name == "atr_trail"
    assert name in EXECUTABLE_EXITS
    holds = {p["max_bars"] for p in param_sets}
    assert holds == {24, 48, 96}           # 1h band
    assert all("k_trail" in p for p in param_sets)


def test_unknown_raises():
    with pytest.raises(ValueError):
        ex.exit_for("1h", "no_such_family")
    with pytest.raises(ValueError):
        ex.exit_for("15m", "reversion_in_range")
