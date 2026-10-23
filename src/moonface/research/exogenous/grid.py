from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateDef:
    name: str
    series_id: str
    lag_days: int
    lookback_days: int
    op: str        # ">" or "<"; comparison of the feature against threshold
    threshold: float
    sign: int      # +1 long BTC, -1 short/flat-BTC when state active (a-priori)


# Publication lags: FRED daily macro typically publishes T+1 business day; use 1.
# Levels use lookback_days=0 (level state); momentum uses 20d.
PRECOMMITTED_STATES: tuple[StateDef, ...] = (
    StateDef("equity_riskon", "SP500", 1, 20, ">", 0.0, +1),       # 20d SP500 up
    StateDef("dollar_weak", "DTWEXBGS", 1, 20, "<", 0.0, +1),      # 20d USD down
    StateDef("vix_low", "VIXCLS", 1, 0, "<", 20.0, +1),            # calm
    StateDef("vix_high", "VIXCLS", 1, 0, ">", 30.0, -1),           # stress
)

# DSR deflation count: the precommitted states plus the two derived states added
# in the screen (yield-curve, dvol-premium) = full search breadth.
N_TRIALS: int = len(PRECOMMITTED_STATES) + 2
