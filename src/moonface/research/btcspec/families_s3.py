"""Frozen explore-phase config grid for the BTC-Specialized lane, Slice 3
(15m/30m intraday-only). Three pinned price families — none reused from Slices 1-2 —
crossed with PER-FAMILY-matched exits: TF-scaled trend exits (atr_trail/donchian_trail/
chandelier, max hold capped at ONE day) for the vol_compression_breakout thrust; a
fixed_bracket (k_stop x m_tp) for the two fade families (liquidity_sweep_reclaim,
bb_revert), where the bracket itself is the exit. fixed_bracket keeps its frozen
internal 96-bar safety cap (exactly 1d at 15m; a 2d worst case at 30m reached only
when neither bracket leg fills first). A config's `group` fixes everything except the
1-D swept entry axis and is single-family, so the selection-stage parameter-island
check compares only within-family axis neighbours. Reuses the Slice-1 ExploreConfig
shape; adds nothing to EXIT_REGISTRY (fixed_bracket already resolves)."""
from __future__ import annotations

from moonface.research.btcspec.exits_scaled import S3_TIMEFRAMES, exit_sets
from moonface.research.btcspec.families import ExploreConfig

S3_FAMILIES = ("vol_compression_breakout", "liquidity_sweep_reclaim", "bb_revert")

# nonoverlap event horizon per Slice-3 timeframe (bars); one day of bars each
_TF_H_S3 = {"15m": 96, "30m": 48}

_AXIS_NAME_S3 = {"vol_compression_breakout": "squeeze_n",
                 "liquidity_sweep_reclaim": "swing_n", "bb_revert": "period"}

_AP = 14  # atr_period, frozen across Slice-3 entries/exits


def _bracket_exits() -> list[tuple[str, dict]]:
    """fixed_bracket grid for the fade families: the bracket is the exit (no hold
    scaling). Same frozen k_stop x m_tp grid as Slice 2's vol_expansion."""
    out: list[tuple[str, dict]] = []
    for k_stop in (1.0, 2.0):
        for m_tp in (2.0, 3.0, 4.0):
            out.append(("fixed_bracket",
                        {"k_stop": k_stop, "m_tp": m_tp, "atr_period": _AP}))
    return out


def _entry_points_s3(family: str) -> list[tuple[float, dict, str]]:
    """(axis_value, entry_params, frozen_group_sig) for a Slice-3 family's wide grid."""
    if family == "vol_compression_breakout":
        return [(float(n), {"squeeze_n": n, "atr_period": _AP, "k": 1.5}, "")
                for n in (16, 32, 64, 96)]
    if family == "liquidity_sweep_reclaim":
        return [(float(n), {"swing_n": n}, "") for n in (16, 32, 64, 96)]
    if family == "bb_revert":
        out: list[tuple[float, dict, str]] = []
        for mult in (2.0, 2.5):
            for period in (24, 48, 96):
                out.append((float(period), {"period": period, "mult": mult},
                            f"mult={mult}"))
        return out
    raise ValueError(f"unsupported family {family!r}")


def _exits_for_family(family: str, timeframe: str) -> list[tuple[str, dict]]:
    if family == "vol_compression_breakout":
        return exit_sets(timeframe)
    return _bracket_exits()


def _exit_sig_s3(exit_name: str, ep: dict) -> str:
    """Stable exit signature; tolerates exits with no max_bars (fixed_bracket)."""
    if "max_bars" in ep:
        body = ",".join(f"{k}={ep[k]}" for k in sorted(ep) if k != "max_bars")
        return f"{exit_name}:mb={ep['max_bars']}:{body}"
    body = ",".join(f"{k}={ep[k]}" for k in sorted(ep))
    return f"{exit_name}:{body}"


def configs_for_s3(timeframe: str) -> list[ExploreConfig]:
    if timeframe not in _TF_H_S3:
        raise ValueError(f"unsupported Slice-3 timeframe {timeframe!r}")
    out: list[ExploreConfig] = []
    h = _TF_H_S3[timeframe]
    for family in S3_FAMILIES:
        axis_name = _AXIS_NAME_S3[family]
        for axis, params, fsig in _entry_points_s3(family):
            for exit_name, ep in _exits_for_family(family, timeframe):
                esig = _exit_sig_s3(exit_name, ep)
                group = f"{timeframe}:{family}:{fsig}:{esig}"
                label = f"{timeframe}:{family}:{axis_name}={axis}:{esig}"
                if fsig:
                    label += f":{fsig}"
                out.append(ExploreConfig(
                    label=label, timeframe=timeframe, family=family,
                    params=dict(params), exit_name=exit_name, exit_params=dict(ep),
                    h=h, group=group, axis=float(axis)))
    return out


def all_explore_configs_s3() -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for tf in S3_TIMEFRAMES:
        out.extend(configs_for_s3(tf))
    return out
