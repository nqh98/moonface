from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

H = 48
EXIT_NAME = "atr_trail"
EXIT_PARAMS = {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}

_LONG_THR = 0.55
_SHORT_THR = 0.45
_LOW_BAND = 0.40
_HIGH_BAND = 0.60
_BASE_PERIOD = 50

_FAMILY_AXES = {
    "pct_above_ma": (20, 50, 100),
    "breadth_momentum": (6, 12, 24),
    "breadth_thrust": (3, 6, 12),
}


@dataclass(frozen=True)
class BreadthCell:
    key: str
    family: str
    axis: int
    long_thr: float
    short_thr: float
    low_band: float
    high_band: float
    base_period: int
    h: int
    exit_name: str
    exit_params: MappingProxyType


def all_cells() -> list[BreadthCell]:
    cells: list[BreadthCell] = []
    for family, axes in _FAMILY_AXES.items():
        for axis in axes:
            cells.append(
                BreadthCell(
                    key=f"{family}:{axis:g}",
                    family=family,
                    axis=axis,
                    long_thr=_LONG_THR,
                    short_thr=_SHORT_THR,
                    low_band=_LOW_BAND,
                    high_band=_HIGH_BAND,
                    base_period=_BASE_PERIOD,
                    h=H,
                    exit_name=EXIT_NAME,
                    exit_params=MappingProxyType(dict(EXIT_PARAMS)),
                )
            )
    return cells
