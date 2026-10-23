import pytest

from moonface.research.btcspec.exits_scaled import (TF_MAX_HOLD_BARS, TIMEFRAMES,
                                                    exit_sets)


def test_tf_max_hold_matches_wall_clock_bands():
    # 2h = 12 bars/day -> 3d/7d/14d ; 4h = 6 bars/day -> 5d/10d/20d
    assert TF_MAX_HOLD_BARS["2h"] == [36, 84, 168]
    assert TF_MAX_HOLD_BARS["4h"] == [30, 60, 120]
    assert TIMEFRAMES == ["2h", "4h"]


def test_exit_sets_cover_three_exits_scaled_per_hold():
    sets = exit_sets("4h")
    names = {name for name, _ in sets}
    assert names == {"atr_trail", "donchian_trail", "chandelier"}
    # every exit param dict carries a TF-scaled max_bars from the 4h band
    for _name, ep in sets:
        assert ep["max_bars"] in TF_MAX_HOLD_BARS["4h"]
        assert ep["atr_period"] == 14
    # 3 holds x (2 atr_trail + 2 donchian_trail + 2 chandelier) = 18
    assert len(sets) == 18


def test_unknown_timeframe_raises():
    with pytest.raises(ValueError):
        exit_sets("5m")  # 5m is not a lane timeframe (1h/2h/4h swing-hold band)
