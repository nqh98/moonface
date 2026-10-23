from moonface.research.regime_overlay.grid import (CELLS, N_TRIALS, TRAIN_END,
                                                   TRAIN_START)
from moonface.research.regime_overlay.overlay import MODES
from moonface.research.regime_overlay.regime import REGIME_DEFS


def test_grid_is_full_cross_product_of_12():
    assert len(CELLS) == 12
    assert N_TRIALS == 12
    assert len({c.cell_id for c in CELLS}) == 12
    expected = {f"{r.id}-{m}" for r in REGIME_DEFS for m in MODES}
    assert {c.cell_id for c in CELLS} == expected


def test_windows_are_ordered():
    assert TRAIN_START < TRAIN_END
