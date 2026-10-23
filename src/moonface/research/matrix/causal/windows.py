"""Embargoed walk-forward windows over bar positions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class WalkWindow:
    index: int
    train_lo: int
    train_hi: int
    test_lo: int
    test_hi: int


def walk_windows(
    n: int,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    gap_bars: int,
) -> Iterator[WalkWindow]:
    start = train_bars
    index = 0
    while start + gap_bars + test_bars <= n:
        yield WalkWindow(
            index=index,
            train_lo=start - train_bars,
            train_hi=start,
            test_lo=start + gap_bars,
            test_hi=start + gap_bars + test_bars,
        )
        index += 1
        start += step_bars
