from moonface.research.btcspec.exits_scaled import (S2_TIMEFRAMES, TF_MAX_HOLD_BARS,
                                                    TIMEFRAMES, exit_sets)


def test_1h_band_added_and_slice1_bands_unchanged():
    assert TF_MAX_HOLD_BARS["1h"] == [24, 48, 96]
    # Slice-1 frozen values must be byte-identical
    assert TF_MAX_HOLD_BARS["2h"] == [36, 84, 168]
    assert TF_MAX_HOLD_BARS["4h"] == [30, 60, 120]
    assert TIMEFRAMES == ["2h", "4h"]
    assert S2_TIMEFRAMES == ["1h"]


def test_exit_sets_1h_has_18_tf_scaled_trend_exits():
    sets = exit_sets("1h")
    assert len(sets) == 18  # 3 holds x (2 atr_trail + 2 donchian_trail + 2 chandelier)
    names = {name for name, _ in sets}
    assert names == {"atr_trail", "donchian_trail", "chandelier"}
    for _name, ep in sets:
        assert ep["max_bars"] in TF_MAX_HOLD_BARS["1h"]
        assert ep["atr_period"] == 14
