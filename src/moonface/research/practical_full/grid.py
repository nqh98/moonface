"""Comprehensive BTC price-family explore grid for the practical-full re-eval.

Every sweepable price family in entries.PRICE_FAMILIES, crossed with
family-matched exits (including alternative TREND exits — atr_trail AND
chandelier), each as a 3-point axis sweep so the selection-stage parameter-island
check has neighbours. Max-hold bars are timeframe-scaled. Reuses the practical
lane's ExploreConfig so the existing explore/select/validate internals consume
this grid unchanged. Exit params resolve in EXECUTABLE_EXITS via single_trade_r.
"""
from __future__ import annotations

from moonface.research.practical.families import ExploreConfig

_AP = 14  # atr_period, frozen across the grid

# timeframe -> trend max-hold bars (~10-20 trading days) and mean-revert max-hold.
TF_MB_TREND: dict[str, int] = {"1h": 96, "2h": 120, "4h": 120}
TF_MB_MR: dict[str, int] = {"1h": 48, "2h": 60, "4h": 60}


def _trend_exits(tf: str) -> list[tuple[str, dict]]:
    mb = TF_MB_TREND[tf]
    return [
        ("atr_trail", {"k_trail": 2.0, "max_bars": mb, "atr_period": _AP}),
        ("chandelier", {"atr_mult": 4.0, "max_bars": mb, "atr_period": _AP}),
    ]


def _mr_exits(tf: str) -> list[tuple[str, dict]]:
    mb = TF_MB_MR[tf]
    return [
        ("mean_revert_reclaim",
         {"ref": "ema", "ref_n": 20, "k_stop": 2.5, "max_bars": mb, "atr_period": _AP}),
        ("fixed_bracket", {"k_stop": 2.0, "m_tp": 4.0, "atr_period": _AP}),
    ]


# family -> (axis_name, axis_values, frozen_params, h, exit_kind)
# exit_kind: "trend" -> atr_trail + chandelier ; "mr" -> mean_revert + fixed_bracket
_FAMILIES: dict[str, tuple] = {
    "ma_cross":               ("slow", [50, 100, 200], {"fast": 20}, 48, "trend"),
    "price_vs_ma":            ("period", [50, 100, 200], {}, 48, "trend"),
    "roc_sign":               ("period", [12, 24, 48], {}, 24, "trend"),
    "donchian_break":         ("n", [20, 55, 100], {}, 48, "trend"),
    "atr_channel_break":      ("k", [1.0, 1.5, 2.0], {"atr_period": _AP}, 48, "trend"),
    "vol_regime":             ("window", [24, 48, 96],
                               {"mode": "low", "trend_n": 50}, 24, "trend"),
    "vol_compression_breakout": ("squeeze_n", [16, 24, 32],
                                 {"atr_period": _AP, "k": 1.0}, 48, "trend"),
    "vol_expansion":          ("mult", [2.0, 2.5, 3.0],
                               {"atr_period": _AP, "lookback": 24}, 24, "trend"),
    "trend_pullback":         ("pull_atr", [0.5, 1.0, 1.5],
                               {"ma": 48, "atr_period": _AP}, 48, "trend"),
    "reversion_in_range":     ("period", [10, 14, 21],
                               {"low": 25, "high": 75}, 24, "mr"),
    "liquidity_sweep_reclaim": ("swing_n", [10, 20, 40], {}, 24, "mr"),
}


def _exit_sig(exit_params: dict) -> str:
    return ",".join(f"{k}={exit_params[k]}" for k in sorted(exit_params)
                    if k != "max_bars")


def configs_for(tf: str) -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for family, (axis_name, axis_values, frozen, h, kind) in _FAMILIES.items():
        exits = _trend_exits(tf) if kind == "trend" else _mr_exits(tf)
        for exit_name, ep in exits:
            sig = _exit_sig(ep)
            group = f"{tf}:{family}:{exit_name}:{sig}"
            for v in axis_values:
                params = {**frozen, axis_name: v}
                label = f"{tf}:{family}:{axis_name}={v}:{exit_name}:{sig}"
                out.append(ExploreConfig(
                    label=label, timeframe=tf, family=family, params=params,
                    exit_name=exit_name, exit_params=dict(ep), h=h,
                    group=group, axis=float(v)))
    return out


def all_configs(timeframes: list[str]) -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for tf in timeframes:
        out.extend(configs_for(tf))
    return out
