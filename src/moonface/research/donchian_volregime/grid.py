"""Frozen constants + cell grid for the donchian_volregime lane.

Windows/floors/robustness are imported from donchian_filter so this lane stays
byte-comparable to the closed ADX-gate control.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from moonface.research.donchian_filter.grid import (  # noqa: F401 (re-exported)
    ACTIVITY_FRAC,
    HOLDOUT_MIN_TRADES,
    QUARTER_BARS,
    SEALED_END,
    SYMBOL,
    TF,
    TRAIN_END,
    TRAIN_START,
    TREND_CAPTURE_FRAC,
    VALIDATE_END,
    YEAR_BARS,
)

if TYPE_CHECKING:
    from tools.engine.swing_donchian import TrendParams

# Frozen feature thresholds (spec §3).
PCT_HI = 0.60
EXPANSION_MIN = 1.00
PCT_WINDOW = 180
ATR_SHORT = 14
ATR_LONG = 100
HV_PERIOD = 20
DON_N = 40

CFG = {
    "pct_hi": PCT_HI,
    "expansion_min": EXPANSION_MIN,
    "pct_window": PCT_WINDOW,
    "atr_short": ATR_SHORT,
    "atr_long": ATR_LONG,
    "hv_period": HV_PERIOD,
    "don_n": DON_N,
}

# Frozen 5-cell grid (spec §4). Order fixed.
CELLS = ("atr_pct", "hv_pct", "expansion", "not_compressed", "hivol_expansion")
N_TRIALS = len(CELLS)


def deployed_base() -> "TrendParams":
    """The byte-frozen Donchian 40/20 spine, identical to donchian_filter."""
    from tools.engine.swing_donchian import _BASE

    return replace(_BASE, entry_n=40, trail_n=20)
