from moonface.research.btcspec.exits_scaled import (S2_TIMEFRAMES, S3_TIMEFRAMES,
                                                    TF_MAX_HOLD_BARS, TIMEFRAMES,
                                                    exit_sets)


def test_intraday_bands_added_and_prior_slices_unchanged():
    assert TF_MAX_HOLD_BARS["15m"] == [24, 48, 96]  # 6h/12h/1d
    assert TF_MAX_HOLD_BARS["30m"] == [12, 24, 48]  # 6h/12h/1d
    # prior slices' frozen values must be byte-identical
    assert TF_MAX_HOLD_BARS["1h"] == [24, 48, 96]
    assert TF_MAX_HOLD_BARS["2h"] == [36, 84, 168]
    assert TF_MAX_HOLD_BARS["4h"] == [30, 60, 120]
    assert TIMEFRAMES == ["2h", "4h"]
    assert S2_TIMEFRAMES == ["1h"]
    assert S3_TIMEFRAMES == ["15m", "30m"]


def test_exit_sets_intraday_have_18_tf_scaled_trend_exits():
    for tf in S3_TIMEFRAMES:
        sets = exit_sets(tf)
        assert len(sets) == 18  # 3 holds x (2 atr_trail + 2 donchian_trail + 2 chandelier)
        names = {name for name, _ in sets}
        assert names == {"atr_trail", "donchian_trail", "chandelier"}
        for _name, ep in sets:
            assert ep["max_bars"] in TF_MAX_HOLD_BARS[tf]
            assert ep["atr_period"] == 14


def test_intraday_max_hold_never_exceeds_one_day():
    bars_per_day = {"15m": 96, "30m": 48}
    for tf in S3_TIMEFRAMES:
        assert max(TF_MAX_HOLD_BARS[tf]) <= bars_per_day[tf]
