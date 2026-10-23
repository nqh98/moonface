"""Gate the frozen Donchian trade stream by entry-bar volatility regime."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

# Reuse the byte-identical control machinery.
from moonface.research.donchian_filter.evaluate import (  # noqa: F401
    _field,
    overlapping_robust_frac,
    slice_metrics,
)
from moonface.research.donchian_volregime.features import allow_flags
from moonface.research.donchian_volregime.grid import CFG, deployed_base
from moonface.research.trend_sim import simulate_donchian


def base_trades(candles, funding):
    return simulate_donchian(candles, deployed_base(), funding)


def gate(base: Sequence[Any], flags: Sequence[bool]) -> list[Any]:
    """Strict subset: keep trades whose entry-bar regime flag is True."""
    out: list[Any] = []
    for trade in base:
        idx = int(_field(trade, "entry_index"))
        if 0 <= idx < len(flags) and flags[idx]:
            out.append(trade)
    return out


def cell_flags(candles, cell_id: str) -> list[bool]:
    return allow_flags(candles, cell_id, CFG)
