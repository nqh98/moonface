"""Cell pruning: negative-sign or underpowered train cells go flat."""

from moonface.models.engine.v3.evaluate import prune_cells
from moonface.models.engine.v3.matrix import REGIME_MECHANISM
from moonface.models.engine.v3.regime import DirState, VolState


def _tr(cell, net_r, i=[0]):
    from moonface.models.engine.v3.evaluate import V3Trade

    i[0] += 1
    return V3Trade(
        entry_index=i[0],
        exit_index=i[0] + 1,
        entry_ts_ms=i[0],
        exit_ts_ms=i[0] + 1,
        direction=1,
        mechanism="BREAKOUT",
        quality=0.5,
        risk_fraction=0.005,
        net_r=net_r,
        bars_held=1,
        exit_reason="target",
        cell=cell,
    )


def test_positive_cell_kept_negative_cell_pruned():
    up_norm = "TRENDING_UP/NORMAL"
    dn_norm = "TRENDING_DOWN/NORMAL"
    train = ([_tr(up_norm, 0.2) for _ in range(40)]
             + [_tr(dn_norm, -0.2) for _ in range(40)])
    fitted = prune_cells(train)
    assert fitted[(DirState.TRENDING_UP, VolState.NORMAL)] == "BREAKOUT"
    assert fitted[(DirState.TRENDING_DOWN, VolState.NORMAL)] is None


def test_underpowered_cell_pruned():
    train = [_tr("TRENDING_UP/NORMAL", 0.5) for _ in range(5)]
    fitted = prune_cells(train)
    assert fitted[(DirState.TRENDING_UP, VolState.NORMAL)] is None


def test_already_none_cell_stays_none():
    fitted = prune_cells([])
    assert fitted[(DirState.RANGING, VolState.HIGH)] is None
    assert set(fitted) == set(REGIME_MECHANISM)
