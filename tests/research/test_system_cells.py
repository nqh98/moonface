from collections import Counter

from moonface.research import system_cells as sc
from moonface.research.entries import PRICE_FAMILIES
from moonface.core.exits import EXIT_REGISTRY


def test_timeframes():
    assert sc.TIMEFRAMES == ["15m", "30m", "1h", "2h", "4h"]


def test_every_family_is_known_and_exit_is_research_grade():
    for cell in sc.all_system_cells():
        assert cell.family in PRICE_FAMILIES, cell.label
        # only EXIT_REGISTRY exits (never the deploy-only donchian_trail)
        assert cell.exit_name in EXIT_REGISTRY, cell.label
        assert "atr_period" in cell.exit_params


def test_each_group_has_exactly_three_swept_points():
    cells = sc.all_system_cells()
    per_group = Counter(c.group for c in cells)
    assert per_group, "no cells"
    assert all(v == 3 for v in per_group.values()), per_group


def test_pooled_count_matches_sum_of_timeframes():
    total = sum(len(sc.system_cells_for(tf)) for tf in sc.TIMEFRAMES)
    assert len(sc.all_system_cells()) == total


def test_labels_unique():
    labels = [c.label for c in sc.all_system_cells()]
    assert len(labels) == len(set(labels))
