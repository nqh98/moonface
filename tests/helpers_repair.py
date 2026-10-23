"""Shared synthetic fixtures for the trend-score-repair tests (hermetic)."""
from __future__ import annotations

from moonface.models.engine.calibration import HypoTrade

H = 3_600_000


def ht(i: int, score: int, net_r: float, direction: int = 1,
       vol: str = "normal") -> HypoTrade:
    return HypoTrade(
        entry_index=i, exit_index=i + 5, entry_ts_ms=i * H,
        exit_ts_ms=(i + 5) * H, book="trend", direction=direction,
        score=score, breadth=3, policy="ALLOW", macro_effective="NEUTRAL",
        vol_state=vol, net_r=net_r, bars_held=5, exit_reason="target")
