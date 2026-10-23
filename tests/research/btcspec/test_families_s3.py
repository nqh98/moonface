# tests/research/btcspec/test_families_s3.py
from moonface.research.btcspec.exits_scaled import S3_TIMEFRAMES
from moonface.research.btcspec.families import ExploreConfig
from moonface.research.btcspec.families_s3 import (S3_FAMILIES, all_explore_configs_s3,
                                                   configs_for_s3)
from moonface.research.entries import PRICE_FAMILIES


def test_s3_families_exist_in_price_families():
    for fam in S3_FAMILIES:
        assert fam in PRICE_FAMILIES


def test_s3_families_not_reused_from_prior_slices():
    from moonface.research.btcspec.families import FAMILIES
    from moonface.research.btcspec.families_s2 import S2_FAMILIES
    assert not set(S3_FAMILIES) & set(FAMILIES)
    assert not set(S3_FAMILIES) & set(S2_FAMILIES)


def test_vol_compression_breakout_uses_tf_scaled_trend_exits():
    for tf in S3_TIMEFRAMES:
        rows = [c for c in configs_for_s3(tf) if c.family == "vol_compression_breakout"]
        assert rows
        for c in rows:
            assert c.exit_name in {"atr_trail", "donchian_trail", "chandelier"}
            assert c.params["k"] == 1.5 and c.params["atr_period"] == 14
        assert {c.axis for c in rows} == {16.0, 32.0, 64.0, 96.0}


def test_fade_families_use_fixed_bracket_without_hold_scaling():
    for tf in S3_TIMEFRAMES:
        rows = [c for c in configs_for_s3(tf)
                if c.family in {"liquidity_sweep_reclaim", "bb_revert"}]
        assert rows and all(c.exit_name == "fixed_bracket" for c in rows)
        for c in rows:
            assert "max_bars" not in c.exit_params  # bracket is the exit
            assert set(c.exit_params) == {"k_stop", "m_tp", "atr_period"}


def test_bb_revert_axis_is_period_with_mult_group():
    rows = [c for c in configs_for_s3("15m") if c.family == "bb_revert"]
    assert {c.params["mult"] for c in rows} == {2.0, 2.5}
    by_group: dict[str, set] = {}
    for c in rows:
        by_group.setdefault(c.group, set()).add(c.axis)
    # within a group only the swept period axis varies (>=2 neighbours for the island check)
    assert all(len(axes) >= 2 for axes in by_group.values())


def test_each_group_is_single_family():
    for tf in S3_TIMEFRAMES:
        by_group: dict[str, set] = {}
        for c in configs_for_s3(tf):
            by_group.setdefault(c.group, set()).add(c.family)
        assert all(len(fams) == 1 for fams in by_group.values())


def test_config_counts_per_family_and_total():
    for tf in S3_TIMEFRAMES:
        cfgs = configs_for_s3(tf)
        counts = {f: sum(c.family == f for c in cfgs) for f in S3_FAMILIES}
        assert counts == {"vol_compression_breakout": 72,
                          "liquidity_sweep_reclaim": 24, "bb_revert": 36}
        assert len(cfgs) == 132
    assert len(all_explore_configs_s3()) == 132 * len(S3_TIMEFRAMES)


def test_h_is_one_day_per_timeframe_and_config_type():
    assert all(c.h == 96 for c in configs_for_s3("15m"))
    assert all(c.h == 48 for c in configs_for_s3("30m"))
    assert isinstance(configs_for_s3("15m")[0], ExploreConfig)
