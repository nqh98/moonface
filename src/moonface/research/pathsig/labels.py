"""Per-bar forward path labels, reusing the already-tested event_outcome().

The label is taken in the LONG frame: ret_r is the signed forward return in R,
mae_r (<=0) the worst adverse excursion, mfe_r (>=0) the best favourable
excursion, all over a fixed horizon h. SHORT outcomes are the mirror image and
are derived at evaluation time, not stored."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.research.drift_screen import event_outcome


@dataclass(frozen=True)
class PathLabel:
    ret_r: float
    mae_r: float   # <= 0
    mfe_r: float   # >= 0


def build_labels(candles: list[Candle], h: int,
                 atr_period: int) -> list[PathLabel | None]:
    """One label per candle index. None where the entry is untradeable (no ATR
    unit) or fewer than h future bars exist."""
    labels: list[PathLabel | None] = []
    for i in range(len(candles)):
        out = event_outcome(candles, i, "LONG", h, atr_period)
        labels.append(None if out is None
                      else PathLabel(ret_r=out[0], mae_r=out[1], mfe_r=out[2]))
    return labels
