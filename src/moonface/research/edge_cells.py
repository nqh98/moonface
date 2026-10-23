"""Frozen cell registry for the dual-timeframe price-only edge search.

Params + exits are pre-registered (experiments/edge_search/*/PREREGISTRATION.md)
and MUST NOT be tuned on results — that is the kill-rule discipline. is_retest
flags cells re-running closed 4h ground (honest labelling)."""
from __future__ import annotations

from moonface.research.edge_search import Cell

_TRAIL = {"atr_period": 14, "k_trail": 2.0, "max_bars": 24}
_BRACKET = {"atr_period": 14, "k_stop": 2.0, "m_tp": 3.0}


def _common(is_retest: bool, test_bars: int, step_bars: int, h: int) -> list[Cell]:
    return [
        Cell("ma_cross_20_50", "ma_cross", {"fast": 20, "slow": 50},
             "atr_trail", _TRAIL, h, test_bars, step_bars, is_retest),
        Cell("donchian_break_n40", "donchian_break", {"n": 40, "long_only": True},
             "donchian_trail",
             {"atr_period": 14, "k_stop": 2.0, "trail_n": 20, "max_bars": 60},
             h, test_bars, step_bars, is_retest),
        Cell("atr_channel_break_k1", "atr_channel_break",
             {"k": 1.0, "atr_period": 14}, "atr_trail", _TRAIL,
             h, test_bars, step_bars, is_retest),
        Cell("reversion_in_range_30", "reversion_in_range",
             {"period": 30, "low": 0.15, "high": 0.85}, "fixed_bracket",
             _BRACKET, h, test_bars, step_bars, is_retest),
    ]


def cells_for(timeframe: str) -> list[Cell]:
    if timeframe == "4h":
        # ~1y test windows on 4h (2190 bars/yr); holdout handled by the CLI.
        return _common(is_retest=True, test_bars=540, step_bars=540, h=12)
    if timeframe == "15m":
        # 15m: ~1 month test windows (2880 bars), shorter horizon, + session family.
        cells = _common(is_retest=False, test_bars=2880, step_bars=2880, h=12)
        cells.append(
            Cell("seasonality_hour", "seasonality",
                 {"hours": [13, 14, 15], "trend_n": 50},
                 "horizon_hold", {"atr_period": 14, "n_bars": 12},
                 12, 2880, 2880, is_retest=False))
        return cells
    raise ValueError(f"unknown timeframe {timeframe!r}")
