"""Frozen explore-phase config grid for the practical lane (thin slice).

Two pinned entry families — reversion_in_range (mean-reversion) and
atr_channel_break (trend/breakout) — each crossed with its TF-scaled,
family-matched exit param sets. A config's `group` fixes everything except the
swept entry axis, so the selection stage can run the parameter-island check over
the three axis points within a group."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.research.practical.exits_scaled import TIMEFRAMES, exit_for

ENTRY_SWEEPS: dict[str, tuple[str, list]] = {
    "reversion_in_range": ("period", [10, 14, 21]),
    "atr_channel_break": ("k", [1.0, 1.5, 2.0]),
}
ENTRY_FROZEN: dict[str, dict] = {
    "reversion_in_range": {"low": 25, "high": 75},
    "atr_channel_break": {"atr_period": 14},
}
# event horizon h for nonoverlap, per family (mean-rev shorter, trend longer)
_FAMILY_H = {"reversion_in_range": 24, "atr_channel_break": 48}


@dataclass(frozen=True)
class ExploreConfig:
    label: str
    timeframe: str
    family: str
    params: dict
    exit_name: str
    exit_params: dict
    h: int
    group: str
    axis: float


def _exit_sig(exit_params: dict) -> str:
    return ",".join(f"{k}={exit_params[k]}" for k in sorted(exit_params)
                    if k != "max_bars")


def configs_for(timeframe: str) -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for family, (axis_name, axis_values) in ENTRY_SWEEPS.items():
        exit_name, exit_param_sets = exit_for(timeframe, family)
        frozen = ENTRY_FROZEN[family]
        h = _FAMILY_H[family]
        for ep in exit_param_sets:
            mb = ep["max_bars"]
            group = f"{timeframe}:{family}:{exit_name}:mb={mb}:{_exit_sig(ep)}"
            for v in axis_values:
                params = {**frozen, axis_name: v}
                label = (f"{timeframe}:{family}:{axis_name}={v}:"
                         f"{exit_name}:mb={mb}:{_exit_sig(ep)}")
                out.append(ExploreConfig(
                    label=label, timeframe=timeframe, family=family,
                    params=params, exit_name=exit_name, exit_params=dict(ep),
                    h=h, group=group, axis=float(v)))
    return out


def all_explore_configs() -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for tf in TIMEFRAMES:
        out.extend(configs_for(tf))
    return out
