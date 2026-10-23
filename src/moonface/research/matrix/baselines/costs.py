from __future__ import annotations

from dataclasses import dataclass

TAKER_FEE = 0.0004
SLIPPAGE_BPS = 1.0


@dataclass(frozen=True)
class CostModel:
    """Per-fill fee + slippage with a simple stress multiplier."""

    taker_fee: float = TAKER_FEE
    slippage_bps: float = SLIPPAGE_BPS
    mult: float = 1.0

    def round_trip(self) -> float:
        per_side = self.taker_fee + self.slippage_bps / 1e4
        return per_side * 2.0 * self.mult
