"""Frozen, pre-registered cell grid for the BTC system-level search.

Each (timeframe, family) GROUP carries exactly ONE swept primary parameter over
3 coarse points (for the plateau rule); all other params are frozen. The total
across all timeframes (len(all_system_cells())) is the pooled DSR n_trials. Only
EXIT_REGISTRY exits are used — the deploy-only trailing exit is excluded so the
research search never perturbs DSR calibration and never touches the frozen
Donchian Slice-3 strategy."""
from __future__ import annotations

from dataclasses import dataclass

TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h"]

_AP = 14  # atr_period, frozen across all exits


@dataclass(frozen=True)
class SystemCell:
    label: str
    timeframe: str
    family: str
    params: dict
    exit_name: str
    exit_params: dict
    h: int
    test_bars: int
    step_bars: int
    group: str
    swept: float
    is_retest: bool


# (family, swept_param_name, [3 values], frozen_other_params, exit_name,
#  exit_params, h, is_retest) per timeframe. `is_retest` = re-tests closed ground
# vs. a genuinely-untested variant (honest labelling, not a gate).
_GRID: dict[str, list[tuple]] = {
    "15m": [
        ("reversion_in_range", "period", [10, 14, 21],
         {"low": 25, "high": 75}, "horizon_hold", {"n_bars": 12, "atr_period": _AP}, 12, True),
        ("donchian_break", "n", [20, 30, 48],
         {"long_only": False}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("vol_compression_breakout", "squeeze_n", [16, 24, 32],
         {"atr_period": _AP, "k": 1.5}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, False),
        ("seasonality", "trend_n", [20, 50, 100],
         {"hours": [13, 14, 15, 16, 17]}, "horizon_hold",
         {"n_bars": 12, "atr_period": _AP}, 12, False),
        ("liquidity_sweep_reclaim", "swing_n", [16, 24, 32],
         {}, "breakeven_horizon", {"n_bars": 24, "k_stop": 3.0, "atr_period": _AP}, 24, False),
    ],
    "30m": [
        ("reversion_in_range", "period", [10, 14, 21],
         {"low": 25, "high": 75}, "horizon_hold", {"n_bars": 12, "atr_period": _AP}, 12, True),
        ("donchian_break", "n", [20, 30, 48],
         {"long_only": False}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("vol_compression_breakout", "squeeze_n", [16, 24, 32],
         {"atr_period": _AP, "k": 1.5}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, False),
        ("seasonality", "trend_n", [20, 50, 100],
         {"hours": [13, 14, 15, 16, 17]}, "horizon_hold",
         {"n_bars": 12, "atr_period": _AP}, 12, False),
        ("liquidity_sweep_reclaim", "swing_n", [16, 24, 32],
         {}, "breakeven_horizon", {"n_bars": 24, "k_stop": 3.0, "atr_period": _AP}, 24, False),
    ],
    "1h": [
        ("roc_sign", "period", [12, 24, 48],
         {}, "atr_trail", {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("atr_channel_break", "k", [1.0, 1.5, 2.0],
         {"atr_period": _AP}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("trend_pullback", "pull_atr", [0.5, 1.0, 1.5],
         {"ma": 50, "atr_period": _AP}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, False),
        ("vol_expansion", "mult", [1.5, 2.0, 2.5],
         {"atr_period": _AP, "lookback": 20}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, False),
        ("vol_regime", "window", [24, 48, 96],
         {"mode": "high", "trend_n": 50}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
    ],
    "2h": [
        ("roc_sign", "period", [12, 24, 48],
         {}, "atr_trail", {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("atr_channel_break", "k", [1.0, 1.5, 2.0],
         {"atr_period": _AP}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("trend_pullback", "pull_atr", [0.5, 1.0, 1.5],
         {"ma": 50, "atr_period": _AP}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, False),
        ("vol_expansion", "mult", [1.5, 2.0, 2.5],
         {"atr_period": _AP, "lookback": 20}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, False),
        ("vol_regime", "window", [24, 48, 96],
         {"mode": "high", "trend_n": 50}, "atr_trail",
         {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
    ],
    "4h": [
        ("ma_cross", "slow", [50, 100, 200],
         {"fast": 20}, "atr_trail", {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("donchian_break", "n", [20, 55, 100],
         {"long_only": True}, "atr_trail",
         {"k_trail": 3.0, "max_bars": 48, "atr_period": _AP}, 24, True),
        ("atr_channel_break", "k", [1.0, 1.5, 2.0],
         {"atr_period": _AP}, "horizon_wide_stop",
         {"n_bars": 24, "k_stop": 2.5, "atr_period": _AP}, 24, True),
        ("vol_regime", "window", [24, 48, 96],
         {"mode": "low", "trend_n": 50}, "horizon_wide_stop",
         {"n_bars": 24, "k_stop": 3.0, "atr_period": _AP}, 24, True),
    ],
}


def system_cells_for(timeframe: str) -> list[SystemCell]:
    cells: list[SystemCell] = []
    for (family, swept_name, values, frozen, exit_name, exit_params, h,
         is_retest) in _GRID[timeframe]:
        group = f"{timeframe}:{family}"
        for v in values:
            params = {**frozen, swept_name: v}
            cells.append(SystemCell(
                label=f"{group}:{swept_name}={v}", timeframe=timeframe,
                family=family, params=params, exit_name=exit_name,
                exit_params=dict(exit_params), h=h, test_bars=_TEST_BARS[timeframe],
                step_bars=_STEP_BARS[timeframe], group=group, swept=float(v),
                is_retest=is_retest))
    return cells


def all_system_cells() -> list[SystemCell]:
    out: list[SystemCell] = []
    for tf in TIMEFRAMES:
        out.extend(system_cells_for(tf))
    return out


def group_key(cell: SystemCell) -> str:
    return cell.group


# Walk-forward window sizing per timeframe (bars). Larger for slower TFs so a
# test window still spans comparable wall-clock; frozen.
_TEST_BARS = {"15m": 2000, "30m": 1500, "1h": 1000, "2h": 750, "4h": 500}
_STEP_BARS = {"15m": 1000, "30m": 750, "1h": 500, "2h": 375, "4h": 250}
