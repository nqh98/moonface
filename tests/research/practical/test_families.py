from collections import Counter

from moonface.core.exits import EXECUTABLE_EXITS
from moonface.research.entries import PRICE_FAMILIES
from moonface.research.practical import families as fam


def test_families_known_and_exits_resolve():
    for c in fam.all_explore_configs():
        assert c.family in PRICE_FAMILIES, c.label
        assert c.exit_name in EXECUTABLE_EXITS, c.label
        assert "atr_period" in c.exit_params


def test_axis_values_match_entry_sweep():
    cfgs = [c for c in fam.configs_for("4h") if c.family == "reversion_in_range"]
    axes = {c.axis for c in cfgs}
    assert axes == {10.0, 14.0, 21.0}
    # frozen low/high present on every reversion config
    assert all(c.params["low"] == 25 and c.params["high"] == 75 for c in cfgs)


def test_each_group_holds_all_three_axis_points():
    # island grouping: a group differs only by the swept entry axis -> size 3
    per_group = Counter(c.group for c in fam.all_explore_configs())
    assert per_group
    assert all(v == 3 for v in per_group.values()), per_group


def test_labels_unique_and_counts():
    cfgs = fam.all_explore_configs()
    assert len({c.label for c in cfgs}) == len(cfgs)
    # 2 TFs x 2 families x 3 entry x 6 exit = 72 configs
    assert len(cfgs) == 72
