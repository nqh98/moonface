"""Rule-based regime labels from a-priori thresholds.

The thresholds are frozen in the design spec and must never be tuned
against study outcomes — that would turn the microscope into a fitted
regime model, which is exactly what it is not."""
from __future__ import annotations

from moonface.research.microscope.factors import FACTOR_NAMES

TREND_THR = 0.5
VOL_THR = 0.5
CROWD_THR = 1.0
UNLABELED = "UNLABELED"


def label(state: dict[str, float | None]) -> str:
    if any(state.get(name) is None for name in FACTOR_NAMES):
        return UNLABELED
    t = state["trend"]
    v = state["vol"]
    c = state["crowding"]
    trend = "UP" if t > TREND_THR else ("DOWN" if t < -TREND_THR else "RANGE")
    vol = "HIGH" if v > VOL_THR else ("LOW" if v < -VOL_THR else "MID")
    crowd = ("CROWDED_LONG" if c > CROWD_THR
             else ("CROWDED_SHORT" if c < -CROWD_THR else "NEUTRAL"))
    return f"{trend}/{vol}/{crowd}"


def label_series(
        states: dict[str, list[dict[str, float | None]]]
) -> dict[str, list[str]]:
    return {sym: [label(s) for s in rows] for sym, rows in states.items()}
