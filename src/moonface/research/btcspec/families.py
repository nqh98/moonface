"""Frozen explore-phase config grid for the BTC-Specialized lane, Slice 1
(2h/4h trend + breakout). Three pinned price entry families crossed with the
TF-scaled trend exits. A config's `group` fixes everything except the 1-D swept entry
axis so the selection stage can run the parameter-island check over axis neighbours."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.research.btcspec.exits_scaled import TIMEFRAMES, exit_sets

FAMILIES = ("donchian_break", "ma_cross", "atr_channel_break")

# nonoverlap event horizon per timeframe (bars)
_TF_H = {"2h": 48, "4h": 30}

_AXIS_NAME = {"donchian_break": "n", "ma_cross": "slow", "atr_channel_break": "k"}


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


def _entry_points(family: str) -> list[tuple[float, dict, str]]:
    """(axis_value, entry_params, frozen_group_sig) for a family's wide grid."""
    if family == "donchian_break":
        return [(float(n), {"n": n}, "") for n in (20, 40, 55, 80, 110)]
    if family == "ma_cross":
        return [(float(s), {"fast": s // 4, "slow": s}, "") for s in (50, 100, 150, 200)]
    if family == "atr_channel_break":
        out: list[tuple[float, dict, str]] = []
        for ap in (14, 20):
            for k in (1.0, 1.5, 2.0, 2.5, 3.0):
                out.append((k, {"k": k, "atr_period": ap}, f"ap={ap}"))
        return out
    raise ValueError(f"unsupported family {family!r}")


def _exit_sig(exit_name: str, ep: dict) -> str:
    body = ",".join(f"{k}={ep[k]}" for k in sorted(ep) if k != "max_bars")
    return f"{exit_name}:mb={ep['max_bars']}:{body}"


def configs_for(timeframe: str) -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    h = _TF_H[timeframe]
    for family in FAMILIES:
        axis_name = _AXIS_NAME[family]
        for axis, params, fsig in _entry_points(family):
            for exit_name, ep in exit_sets(timeframe):
                esig = _exit_sig(exit_name, ep)
                group = f"{timeframe}:{family}:{fsig}:{esig}"
                label = f"{timeframe}:{family}:{axis_name}={axis}:{esig}"
                if fsig:
                    label += f":{fsig}"
                out.append(ExploreConfig(
                    label=label, timeframe=timeframe, family=family,
                    params=dict(params), exit_name=exit_name, exit_params=dict(ep),
                    h=h, group=group, axis=float(axis)))
    return out


def all_explore_configs() -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for tf in TIMEFRAMES:
        out.extend(configs_for(tf))
    return out
