"""Frozen 9 center components for the portfolio tournament (1h+4h price centers)."""
from __future__ import annotations

from moonface.research.system_cells import system_cells_for, SystemCell

TIMEFRAMES = ("1h", "4h")


def center_components() -> list[SystemCell]:
    """The median-'swept' center cell per (timeframe, family) on 1h and 4h.

    Components are inputs (frozen), never the search. Returned in a stable
    order: 1h families in system_cells order, then 4h families.
    """
    out: list[SystemCell] = []
    for tf in TIMEFRAMES:
        cells = system_cells_for(tf)
        families: dict[str, list[SystemCell]] = {}
        for c in cells:
            families.setdefault(c.family, []).append(c)
        for family in families:  # insertion order = system_cells grid order
            group = sorted(families[family], key=lambda c: c.swept)
            out.append(group[len(group) // 2])  # median of 3 swept values
    return out
