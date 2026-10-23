"""Frozen constants and leakage-safe chronological segmentation."""
from moonface.models.engine.repair import (
    CI_HI_Q,
    CI_LO_Q,
    FAMILY_ALPHA,
    N_CANDIDATES,
    PURGE_MS,
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    segment_panel,
)

from tests.helpers_repair import H, ht


def test_frozen_boundaries():
    assert TRAIN_END_TS_MS == 1688169600000
    assert SEALED_START_TS_MS == 1748736000000
    assert PURGE_MS == 168 * H
    assert FAMILY_ALPHA == 0.05 and N_CANDIDATES == 3
    assert abs(CI_LO_Q - 0.05 / 3 / 2) < 1e-12
    assert abs(CI_HI_Q - (1.0 - 0.05 / 3 / 2)) < 1e-12


def test_segment_panel_boundaries():
    train_end = 1000 * H
    sealed_start = 2000 * H
    trades = [
        ht(10, 70, 0.5),
        ht(1200, 70, 0.5),
        ht(1001, 70, 0.5),
        ht(2200, 70, 0.5),
        ht(2001, 70, 0.5),
    ]
    segs, dropped = segment_panel(trades, train_end, sealed_start)
    assert [t.entry_index for t in segs["train"]] == [10]
    assert [t.entry_index for t in segs["validation"]] == [1200]
    assert [t.entry_index for t in segs["sealed"]] == [2200]
    assert dropped == 2


def test_trade_spanning_train_boundary_is_dropped():
    segs, dropped = segment_panel([ht(995, 70, 0.5)], 1000 * H, 2000 * H)
    assert dropped == 1
    assert not segs["train"] and not segs["validation"] and not segs["sealed"]
