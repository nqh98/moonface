"""Honest single-path trade attribution for one MTF cell.

The diagnostic econ walk-forward uses overlapping windows (trades counted ~3x),
which inflates the absolute drawdown. For deployability and transfer we want the
faithful single-path equity curve: generate the cell's entries once over the
whole series, resolve each through the frozen exit in time order, and measure the
real running drawdown. Pure module; callers supply candles."""
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.research.mtf.evaluate import iter_trades
from moonface.research.mtf.grid import MtfCell

Trade = tuple[int, str, float]      # (entry_ts_ms, side, net_r)


def trade_stream(candles, cell: MtfCell) -> list[Trade]:
    """Time-ordered (entry_ts, side, net_r) for the cell over the full series,
    one non-overlapping entry per h-bar horizon. Exit resolution (including the
    structural regime_flip exit) is centralized in evaluate.iter_trades."""
    return [(candles[i].timestamp_ms, side, r)
            for i, side, r in iter_trades(candles, cell)]


def path_max_dd(rs: list[float]) -> float:
    """Worst running peak-to-trough of the cumulative R curve (<= 0)."""
    eq = peak = mdd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    return round(mdd, 2)


def period_stats(trades: list[Trade], start_ms: int | None = None,
                 end_ms: int | None = None) -> dict:
    """Summary for trades whose entry falls in [start_ms, end_ms). MAR is
    total_r / |single-path max drawdown|, the f-independent risk-adjusted return."""
    sel = [(ts, side, r) for ts, side, r in trades
           if (start_ms is None or ts >= start_ms)
           and (end_ms is None or ts < end_ms)]
    rs = [r for _, _, r in sel]
    s = summarize_r(rs)
    dd = path_max_dd(rs)
    longs = sum(1 for _, side, _ in sel if side == "LONG")
    return {"n": s.trade_count, "longs": longs, "shorts": s.trade_count - longs,
            "pf": s.profit_factor, "expectancy_r": s.expectancy_r,
            "win_rate": s.win_rate, "total_r": s.total_r, "max_dd_r": dd,
            "mar": round(abs(s.total_r / dd), 4) if dd else 0.0,
            "positive": s.total_r > 0}
