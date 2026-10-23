"""Timeframe-scaled, family-matched exit builder for the practical lane.

The closed 72-cell lane froze exit holds in BARS across all timeframes; this
module fixes that: each (timeframe, family) yields the family-appropriate exit
with max-hold values scaled to the timeframe's wall-clock band (design spec
2026-06-21). Exit names resolve in EXECUTABLE_EXITS (mean_revert_reclaim comes
from PRACTICAL_EXIT_REGISTRY; atr_trail from EXIT_REGISTRY)."""
from __future__ import annotations

TIMEFRAMES = ["1h", "4h"]

# wall-clock bands -> bars:  1h short swing 1-5d -> 1d/2d/4d ; 4h swing 5-20d -> 5d/10d/20d
TF_MAX_HOLD_BARS: dict[str, list[int]] = {"1h": [24, 48, 96], "4h": [30, 60, 120]}

_AP = 14  # atr_period, frozen


def _mean_revert_param_sets(timeframe: str) -> list[dict]:
    sets: list[dict] = []
    for max_bars in TF_MAX_HOLD_BARS[timeframe]:
        for ref in ("ema", "range_mid"):
            sets.append({"ref": ref, "ref_n": 20, "k_stop": 2.5,
                         "max_bars": max_bars, "atr_period": _AP})
    return sets


def _atr_trail_param_sets(timeframe: str) -> list[dict]:
    sets: list[dict] = []
    for max_bars in TF_MAX_HOLD_BARS[timeframe]:
        for k_trail in (2.0, 3.0):
            sets.append({"k_trail": k_trail, "max_bars": max_bars,
                         "atr_period": _AP})
    return sets


def exit_for(timeframe: str, family: str) -> tuple[str, list[dict]]:
    """(exit_name, [exit_params, ...]) family-matched and timeframe-scaled."""
    if timeframe not in TF_MAX_HOLD_BARS:
        raise ValueError(f"unsupported timeframe {timeframe!r}")
    if family == "reversion_in_range":
        return "mean_revert_reclaim", _mean_revert_param_sets(timeframe)
    if family == "atr_channel_break":
        return "atr_trail", _atr_trail_param_sets(timeframe)
    raise ValueError(f"unsupported family {family!r}")
