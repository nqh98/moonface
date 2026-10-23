from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.engine.swing_donchian import TrendParams

ADX_PERIOD = 14
THRESHOLDS = (18, 20, 25)
N_TRIALS = 3

TRAIN_START = 1577836800000
TRAIN_END = 1698796800000
VALIDATE_END = 1740787200000
SEALED_END = 1782300000000

YEAR_BARS = 2190
QUARTER_BARS = 547
TREND_CAPTURE_FRAC = 0.90
ACTIVITY_FRAC = 0.50
HOLDOUT_MIN_TRADES = 10
NEUTRAL_TOL_R = 5.0
SYMBOL = "BTCUSDT"
TF = "4h"


def deployed_base() -> TrendParams:
    from tools.engine.swing_donchian import _BASE

    return replace(_BASE, entry_n=40, trail_n=20)
