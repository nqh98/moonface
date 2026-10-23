"""Timeframe-scaled, trend-family exit builder for the BTC-Specialized lane.

All three exits (atr_trail, donchian_trail, chandelier) are trend/breakout exits and
apply to all Slice-1 entry families. Max-hold values are scaled to each timeframe's
wall-clock band (design spec 2026-06-21): never the closed lane's frozen bar counts.
atr_trail/donchian_trail resolve in EXECUTABLE_EXITS already; chandelier comes from
BTCSPEC_EXIT_REGISTRY."""
from __future__ import annotations

TIMEFRAMES = ["2h", "4h"]
S2_TIMEFRAMES = ["1h"]  # Slice-2 short-swing band (additive; Slice-1 TIMEFRAMES frozen)
S3_TIMEFRAMES = ["15m", "30m"]  # Slice-3 intraday band (additive; prior slices frozen)

# wall-clock bands -> bars.  1h=24 bars/day: 1d/2d/4d ; 2h=12 bars/day: 3d/7d/14d ;
# 4h=6 bars/day: 5d/10d/20d ; intraday-only Slice 3 caps at ONE day:
# 15m=96 bars/day: 6h/12h/1d ; 30m=48 bars/day: 6h/12h/1d
TF_MAX_HOLD_BARS: dict[str, list[int]] = {"15m": [24, 48, 96], "30m": [12, 24, 48],
                                          "1h": [24, 48, 96],
                                          "2h": [36, 84, 168], "4h": [30, 60, 120]}

_AP = 14  # atr_period, frozen across exits


def exit_sets(timeframe: str) -> list[tuple[str, dict]]:
    """(exit_name, exit_params) pairs for all trend exits, TF-scaled max-hold."""
    if timeframe not in TF_MAX_HOLD_BARS:
        raise ValueError(f"unsupported timeframe {timeframe!r}")
    out: list[tuple[str, dict]] = []
    for mb in TF_MAX_HOLD_BARS[timeframe]:
        for k_trail in (2.0, 3.0):
            out.append(("atr_trail",
                        {"k_trail": k_trail, "max_bars": mb, "atr_period": _AP}))
        for trail_n in (10, 20):
            out.append(("donchian_trail",
                        {"k_stop": 2.0, "trail_n": trail_n, "max_bars": mb,
                         "atr_period": _AP}))
        for atr_mult in (3.0, 4.0):
            out.append(("chandelier",
                        {"atr_mult": atr_mult, "max_bars": mb, "atr_period": _AP}))
    return out
