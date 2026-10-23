"""Gate the frozen Donchian trade stream by entry-bar ADX and score slices."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from moonface.core.metrics import summarize_r
from moonface.research.donchian_filter.grid import deployed_base
from moonface.kernel.econ import _mar
from moonface.research.trend_sim import simulate_donchian


def _field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj[name]
    return getattr(obj, name)


def base_trades(candles, funding):
    return simulate_donchian(candles, deployed_base(), funding)


def gate(base: Sequence[Any], adx: Sequence[float], threshold: float) -> list[Any]:
    """Strict subset: keep trades whose entry-bar ADX meets the threshold."""
    out: list[Any] = []
    for trade in base:
        idx = int(_field(trade, "entry_index"))
        if adx[idx] >= threshold:
            out.append(trade)
    return out


def slice_metrics(trades) -> dict:
    rs = [_field(t, "r_multiple") for t in trades]
    s = summarize_r(rs)
    return {
        "n": s.trade_count,
        "net_r": s.total_r,
        "expectancy_r": s.expectancy_r,
        "profit_factor": s.profit_factor,
        "max_dd_r": s.max_drawdown_r,
        "mar": round(_mar(s), 4),
    }


def _alive(summary) -> bool:
    return summary.profit_factor > 1.0 and summary.expectancy_r > 0.0


def overlapping_robust_frac(trades, n_bars, year_bars, step_bars) -> float:
    """Fraction of overlapping year-length windows that are economically alive."""
    if n_bars <= 0 or year_bars <= 0 or step_bars <= 0:
        return 0.0

    total = 0
    alive = 0
    for lo in range(0, n_bars - year_bars + 1, step_bars):
        hi = lo + year_bars
        window = [t for t in trades if lo <= _field(t, "entry_index") < hi]
        total += 1
        if window and _alive(summarize_r([_field(t, "r_multiple") for t in window])):
            alive += 1
    return round(alive / total, 4) if total else 0.0
