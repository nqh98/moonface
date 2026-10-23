from __future__ import annotations

from dataclasses import dataclass

# regime labels
UPTREND = "uptrend"
DOWNTREND = "downtrend"
RANGE_CHOP = "range_chop"
VOL_COMPRESSION = "vol_compression"
VOL_EXPANSION = "vol_expansion"
OVEREXTENDED = "overextended"
NO_TRADE = "no_trade"
SUPPORTIVE = frozenset({UPTREND, VOL_COMPRESSION, VOL_EXPANSION})

# output states
WAIT = "WAIT"
WATCH = "WATCH"
LONG_SETUP = "LONG_SETUP"
LONG_SIGNAL = "LONG_SIGNAL"
INVALID = "INVALID"


@dataclass(frozen=True)
class PlaybookParams:
    # moving averages / structure
    ma_fast: int = 20
    ma_mid: int = 50
    ma_slow: int = 200
    atr_period: int = 14
    slope_n: int = 20            # 4h MA slope lookback (grid axis)
    donchian_n: int = 20         # breakout channel (grid axis)
    donchian_mid_n: int = 55
    # regime thresholds
    atr_pct_window: int = 100
    compress_pct: float = 25.0
    expand_pct: float = 75.0
    slope_eps: float = 0.0005    # |slope| below this = flat (range)
    overext_k: float = 2.5       # close > ma_mid + k*ATR => overextended
    # quality floors
    min_rr: float = 1.5
    max_entry_atr: float = 1.0       # entry already > k*ATR past level => late
    max_risk_atr: float = 2.0        # entry->invalidation max, in ATR
    min_expansion_atr: float = 1.2   # expansion bar range floor, in ATR
    chop_eff_floor: float = 0.3      # efficiency ratio floor over slope_n
