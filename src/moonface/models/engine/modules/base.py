from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from moonface.core.models import Candle
from moonface.models.engine.deriv import DerivSnapshot

Archetype = Literal["trend", "mean_revert", "context"]
__all__ = ["DerivSnapshot", "ModuleScore", "TfViews"]


@dataclass(frozen=True)
class ModuleScore:
    module: str
    direction: int
    points: int
    archetype: Archetype
    data_ok: bool
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError(f"invalid direction for {self.module}: {self.direction}")
        if self.points < 0 or self.points % 5 != 0:
            raise ValueError(f"invalid points for {self.module}: {self.points}")
        if not isinstance(self.evidence, tuple):
            object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True)
class TfViews:
    h1: list[Candle]
    h4: list[Candle]
    d1: list[Candle]
    w1: list[Candle]
