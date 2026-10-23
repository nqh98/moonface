# tests/research/btcspec/test_families_s2.py
from moonface.research.btcspec.exits_scaled import S2_TIMEFRAMES
from moonface.research.btcspec.families import ExploreConfig
from moonface.research.btcspec.families_s2 import (S2_FAMILIES, all_explore_configs_s2,
                                                   configs_for_s2)
from moonface.research.entries import PRICE_FAMILIES


def test_s2_families_exist_in_price_families():
    for fam in S2_FAMILIES:
        assert fam in PRICE_FAMILIES


def test_ma_cross_fast_is_quarter_of_slow():
    for c in (c for c in configs_for_s2("1h") if c.family == "ma_cross"):
        assert c.params["fast"] == c.params["slow"] // 4
        assert c.exit_name in {"atr_trail", "donchian_trail", "chandelier"}


def test_vol_expansion_uses_fixed_bracket_without_hold_scaling():
    rows = [c for c in configs_for_s2("1h") if c.family == "vol_expansion"]
    assert rows and all(c.exit_name == "fixed_bracket" for c in rows)
    for c in rows:
        assert "max_bars" not in c.exit_params  # bracket is the exit
        assert set(c.exit_params) == {"k_stop", "m_tp", "atr_period"}
    # lookback is the frozen group dim; mult is the swept 1-D axis
    assert {c.params["lookback"] for c in rows} == {24, 48}
    assert {c.axis for c in rows} == {1.5, 2.0, 2.5, 3.0}


def test_trend_pullback_axis_is_ma_with_pull_group():
    rows = [c for c in configs_for_s2("1h") if c.family == "trend_pullback"]
    assert {c.params["pull_atr"] for c in rows} == {1.0, 1.5}
    by_group: dict[str, set] = {}
    for c in rows:
        by_group.setdefault(c.group, set()).add(c.axis)
    # within a group only the swept ma axis varies (>=2 neighbours for the island check)
    assert any(len(axes) >= 2 for axes in by_group.values())


def test_each_group_is_single_family():
    cfgs = configs_for_s2("1h")
    by_group: dict[str, set] = {}
    for c in cfgs:
        by_group.setdefault(c.group, set()).add(c.family)
    assert all(len(fams) == 1 for fams in by_group.values())


def test_config_counts_per_family_and_total():
    cfgs = configs_for_s2("1h")
    counts = {f: sum(c.family == f for c in cfgs) for f in S2_FAMILIES}
    assert counts == {"ma_cross": 72, "trend_pullback": 144, "vol_expansion": 48}
    assert len(cfgs) == 264
    assert len(all_explore_configs_s2()) == 264 * len(S2_TIMEFRAMES)


def test_h_is_1h_scaled_and_config_type():
    cfgs = configs_for_s2("1h")
    assert all(c.h == 96 for c in cfgs)
    assert isinstance(cfgs[0], ExploreConfig)
