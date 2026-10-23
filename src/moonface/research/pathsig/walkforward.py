"""Anchored, purged, embargoed walk-forward folds over sample positions.

Sample positions are 0..n_samples-1 (positions into the dataset, not candle
indices). The final lockbox_fraction is the sealed tail and is never part of a
fold. Each test block is separated from training by `embargo` positions on each
side so labels that span future bars cannot leak across the boundary."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fold:
    train_idx: list[int]
    test_idx: list[int]


def walk_forward_folds(n_samples: int, n_folds: int, embargo: int,
                       lockbox_fraction: float) -> list[Fold]:
    usable = int(n_samples * (1.0 - lockbox_fraction))
    if n_folds < 1 or usable < n_folds * (embargo + 2):
        return []
    block = usable // (n_folds + 1)          # first block is the seed train set
    folds: list[Fold] = []
    for k in range(1, n_folds + 1):
        test_lo = block * k
        test_hi = block * (k + 1) if k < n_folds else usable
        test_idx = list(range(test_lo, test_hi))
        train_idx = [i for i in range(0, test_lo - embargo) if i >= 0]
        if not train_idx or not test_idx:
            continue
        folds.append(Fold(train_idx=train_idx, test_idx=test_idx))
    return folds
