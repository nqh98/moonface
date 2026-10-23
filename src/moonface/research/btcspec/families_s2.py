"""Frozen explore-phase config grid for the BTC-Specialized lane, Slice 2
(1h short-swing). Three pinned price families crossed with PER-FAMILY-matched exits:
trend exits (atr_trail/donchian_trail/chandelier, TF-scaled holds) for ma_cross and
trend_pullback; a fixed_bracket (k_stop x m_tp) for the vol_expansion thrust, where the
bracket itself is the exit and TF-scaled holds do not apply. A config's `group` fixes
everything except the 1-D swept entry axis and is single-family, so the selection-stage
parameter-island check compares only within-family axis neighbours. Reuses the Slice-1
ExploreConfig shape; adds nothing to EXIT_REGISTRY (fixed_bracket already resolves)."""
from __future__ import annotations

from moonface.research.btcspec.exits_scaled import S2_TIMEFRAMES, exit_sets
from moonface.research.btcspec.families import ExploreConfig

S2_FAMILIES = ("ma_cross", "trend_pullback", "vol_expansion")

# nonoverlap event horizon per Slice-2 timeframe (bars); 1h=24 bars/day -> 4d
_TF_H_S2 = {"1h": 96}

_AXIS_NAME_S2 = {"ma_cross": "slow", "trend_pullback": "ma", "vol_expansion": "mult"}

_AP = 14  # atr_period, frozen across Slice-2 entries/exits


def _bracket_exits() -> list[tuple[str, dict]]:
    """fixed_bracket grid for vol_expansion: the bracket is the exit (no hold scaling).
    fixed_bracket caps internally at its 96-bar safety cap == the 4d 1h hold."""
    out: list[tuple[str, dict]] = []
    for k_stop in (1.0, 2.0):
        for m_tp in (2.0, 3.0, 4.0):
            out.append(("fixed_bracket",
                        {"k_stop": k_stop, "m_tp": m_tp, "atr_period": _AP}))
    return out


def _entry_points_s2(family: str) -> list[tuple[float, dict, str]]:
    """(axis_value, entry_params, frozen_group_sig) for a Slice-2 family's wide grid."""
    if family == "ma_cross":
        return [(float(s), {"fast": s // 4, "slow": s}, "") for s in (24, 48, 96, 144)]
    if family == "trend_pullback":
        out: list[tuple[float, dict, str]] = []
        for pull in (1.0, 1.5):
            for ma in (24, 48, 96, 144):
                out.append((float(ma),
                            {"ma": ma, "pull_atr": pull, "atr_period": _AP},
                            f"pull={pull}"))
        return out
    if family == "vol_expansion":
        out = []
        for lb in (24, 48):
            for mult in (1.5, 2.0, 2.5, 3.0):
                out.append((mult,
                            {"atr_period": _AP, "lookback": lb, "mult": mult},
                            f"lb={lb}"))
        return out
    raise ValueError(f"unsupported family {family!r}")


def _exits_for_family(family: str, timeframe: str) -> list[tuple[str, dict]]:
    if family == "vol_expansion":
        return _bracket_exits()
    return exit_sets(timeframe)


def _exit_sig_s2(exit_name: str, ep: dict) -> str:
    """Stable exit signature; tolerates exits with no max_bars (fixed_bracket)."""
    if "max_bars" in ep:
        body = ",".join(f"{k}={ep[k]}" for k in sorted(ep) if k != "max_bars")
        return f"{exit_name}:mb={ep['max_bars']}:{body}"
    body = ",".join(f"{k}={ep[k]}" for k in sorted(ep))
    return f"{exit_name}:{body}"


def configs_for_s2(timeframe: str) -> list[ExploreConfig]:
    if timeframe not in _TF_H_S2:
        raise ValueError(f"unsupported Slice-2 timeframe {timeframe!r}")
    out: list[ExploreConfig] = []
    h = _TF_H_S2[timeframe]
    for family in S2_FAMILIES:
        axis_name = _AXIS_NAME_S2[family]
        for axis, params, fsig in _entry_points_s2(family):
            for exit_name, ep in _exits_for_family(family, timeframe):
                esig = _exit_sig_s2(exit_name, ep)
                group = f"{timeframe}:{family}:{fsig}:{esig}"
                label = f"{timeframe}:{family}:{axis_name}={axis}:{esig}"
                if fsig:
                    label += f":{fsig}"
                out.append(ExploreConfig(
                    label=label, timeframe=timeframe, family=family,
                    params=dict(params), exit_name=exit_name, exit_params=dict(ep),
                    h=h, group=group, axis=float(axis)))
    return out


def all_explore_configs_s2() -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for tf in S2_TIMEFRAMES:
        out.extend(configs_for_s2(tf))
    return out
