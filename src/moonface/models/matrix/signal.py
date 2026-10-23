from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    ts_ms: int
    asset: str
    primary: str
    direction: int
    state_tag: str
    horizon_bars: int
    expected_r: float
    conviction: float
    target_exposure: float
