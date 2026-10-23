"""C2 conditional tiering: per-(side, vol) threshold offsets, Train-derived."""
from moonface.models.engine.repair import (
    apply_side_vol_offset,
    fit_side_vol_offsets,
)

from tests.helpers_repair import ht


def _uniform_cells(mean):
    train = []
    i = 0
    for side in (1, -1):
        for vol in ("normal", "high"):
            for _ in range(40):
                train.append(ht(i, 70, mean, direction=side, vol=vol))
                i += 10
    return train


def test_offsets_zero_when_every_cell_matches_pool():
    offs = fit_side_vol_offsets(_uniform_cells(0.1))
    assert set(offs) == {("LONG", "normal"), ("LONG", "high"),
                         ("SHORT", "normal"), ("SHORT", "high")}
    assert all(v == 0 for v in offs.values())


def test_bad_cell_gets_max_offset_when_no_offset_cures_it():
    train = []
    i = 0
    for _ in range(40):
        train.append(ht(i, 70, 0.3))
        i += 10
    for _ in range(40):
        train.append(ht(i, 70, -0.3, direction=-1))
        i += 10
    offs = fit_side_vol_offsets(train)
    assert offs[("LONG", "normal")] == 0
    # every offset either leaves the bad mean below pool or empties the cell
    assert offs[("SHORT", "normal")] == 20
    # cells with no Train data are conservative: max offset
    assert offs[("LONG", "high")] == 20


def test_all_zero_when_pooled_qualifiers_underpowered():
    train = [ht(i * 10, 70, 0.1) for i in range(10)]
    assert all(v == 0 for v in fit_side_vol_offsets(train).values())


def test_apply_side_vol_offset():
    offs = {("LONG", "normal"): 0, ("SHORT", "normal"): 20}
    assert apply_side_vol_offset(ht(0, 70, 0.0), offs) == 70.0
    assert apply_side_vol_offset(ht(0, 70, 0.0, direction=-1), offs) == 50.0
    # missing cell -> offset 0
    assert apply_side_vol_offset(ht(0, 70, 0.0, vol="high"), offs) == 70.0
