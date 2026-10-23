from __future__ import annotations

from dataclasses import dataclass

from moonface.research.regime_overlay.overlay import MODES
from moonface.research.regime_overlay.regime import REGIME_DEFS

TRAIN_START = 1577836800000      # 2020-01-01
TRAIN_END = 1698796800000        # 2023-11-01
VALIDATE_START = TRAIN_END
VALIDATE_END = 1740787200000     # 2025-03-01
SEALED_START = VALIDATE_END
SEALED_END = 1782300000000       # ~2026-06-24

BTC_SYMBOL = "BTCUSDT"
BTC_TF = "4h"
FRED_SERIES = ("SP500", "VIXCLS", "DTWEXBGS")


@dataclass(frozen=True)
class Cell:
    cell_id: str
    regime_id: str
    mode: str


CELLS: tuple[Cell, ...] = tuple(
    Cell(cell_id=f"{r.id}-{m}", regime_id=r.id, mode=m)
    for r in REGIME_DEFS
    for m in MODES
)

N_TRIALS = len(CELLS)
