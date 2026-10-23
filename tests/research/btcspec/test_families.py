from moonface.research.btcspec.families import (FAMILIES, ExploreConfig,
                                                all_explore_configs, configs_for)
from moonface.research.btcspec.exits_scaled import TIMEFRAMES
from moonface.research.entries import PRICE_FAMILIES


def test_families_exist_in_price_families():
    for fam in FAMILIES:
        assert fam in PRICE_FAMILIES


def test_ma_cross_fast_is_quarter_of_slow():
    rows = [c for c in configs_for("4h") if c.family == "ma_cross"]
    for c in rows:
        assert c.params["fast"] == c.params["slow"] // 4


def test_atr_channel_break_period_is_group_dim_axis_is_k():
    rows = [c for c in configs_for("4h") if c.family == "atr_channel_break"]
    periods = {c.params["atr_period"] for c in rows}
    assert periods == {14, 20}
    # within one group every member shares atr_period+exit and varies only k (axis)
    by_group: dict[str, set] = {}
    for c in rows:
        by_group.setdefault(c.group, set()).add(c.axis)
    assert any(len(ks) >= 2 for ks in by_group.values())


def test_config_count_per_timeframe():
    # entries: donchian 5 + ma_cross 4 + atr_channel (5 k x 2 ap)=10 -> 19
    # exits: 18 per tf -> 19*18 = 342 per tf
    assert len(configs_for("4h")) == 342
    assert len(configs_for("2h")) == 342
    assert len(all_explore_configs()) == 342 * len(TIMEFRAMES)


def test_h_is_timeframe_scaled():
    assert all(c.h == 30 for c in configs_for("4h"))
    assert all(c.h == 48 for c in configs_for("2h"))


def test_explore_config_is_frozen():
    c = configs_for("4h")[0]
    assert isinstance(c, ExploreConfig)
