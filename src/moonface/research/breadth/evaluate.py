"""Breadth-lane evaluator for the frozen BTC timing grid."""
from __future__ import annotations

from collections.abc import Callable

from moonface.core.metrics import (
    _kurtosis,
    _sharpe,
    _skew,
    deflated_sharpe,
    single_trade_r,
    summarize_r,
)
from moonface.research.breadth.grid import BreadthCell
from moonface.research.breadth.signals import (
    _ALWAYS,
    breadth_momentum_series,
    entries_from_state,
    level_state,
    pct_above_ma_series,
    thrust_state,
)


def cell_entries(
    daily,
    btc,
    cell: BreadthCell,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> list[tuple[int, str]]:
    if cell.family == "pct_above_ma":
        series = pct_above_ma_series(daily, int(cell.axis), is_member=is_member)
        state = level_state(series, cell.long_thr, cell.short_thr)
    elif cell.family == "breadth_momentum":
        series = breadth_momentum_series(daily, int(cell.axis), is_member=is_member)
        state = level_state(series, cell.long_thr, cell.short_thr)
    elif cell.family == "breadth_thrust":
        series = pct_above_ma_series(daily, int(cell.base_period), is_member=is_member)
        state = thrust_state(series, cell.low_band, cell.high_band, int(cell.axis))
    else:
        raise ValueError(f"unknown breadth family {cell.family!r}")
    return entries_from_state(btc, state, cell.h)


def score_records(btc, entries, exit_name: str, exit_params: dict) -> list[dict]:
    records: list[dict] = []
    for i, side in entries:
        result = single_trade_r(btc, i, side, exit_name, exit_params)
        if result is None:
            continue
        net_r, atr_frac = result
        records.append({"i": i, "side": side, "net_r": net_r, "atr_frac": atr_frac})
    return records


def summarize(records: list[dict]) -> dict:
    rs = [r["net_r"] for r in records]
    longs = [r["net_r"] for r in records if r["side"] == "LONG"]
    shorts = [r["net_r"] for r in records if r["side"] == "SHORT"]
    summary = summarize_r(rs)
    long_summary = summarize_r(longs)
    short_summary = summarize_r(shorts)
    return {
        "trade_count": summary.trade_count,
        "total_r": summary.total_r,
        "expectancy_r": summary.expectancy_r,
        "profit_factor": summary.profit_factor,
        "max_drawdown_r": summary.max_drawdown_r,
        "sharpe": _sharpe(rs) if len(rs) >= 2 else 0.0,
        "skew": _skew(rs) if len(rs) >= 2 else 0.0,
        "kurtosis": _kurtosis(rs) if len(rs) >= 2 else 3.0,
        "long_total_r": round(sum(longs), 4),
        "short_total_r": round(sum(shorts), 4),
        "long_trade_count": len(longs),
        "short_trade_count": len(shorts),
        "long_expectancy_r": long_summary.expectancy_r,
        "short_expectancy_r": short_summary.expectancy_r,
    }


def evaluate_cell(
    daily,
    btc,
    cell: BreadthCell,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> dict:
    entries = cell_entries(daily, btc, cell, is_member=is_member)
    records = score_records(btc, entries, cell.exit_name, cell.exit_params)
    return {
        "key": cell.key,
        "family": cell.family,
        "axis": cell.axis,
        "metrics": summarize(records),
        "records": records,
    }


def run_explore(
    daily,
    btc,
    cells: list[BreadthCell],
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> list[dict]:
    rows = [evaluate_cell(daily, btc, cell, is_member=is_member) for cell in cells]
    rows.sort(key=lambda row: row["metrics"]["total_r"], reverse=True)
    trial_srs = [row["metrics"]["sharpe"] for row in rows if row["metrics"]["trade_count"] >= 2]
    n_trials = len(cells)
    for row in rows:
        metrics = row["metrics"]
        row["dsr"] = deflated_sharpe(
            metrics["sharpe"],
            max(2, metrics["trade_count"]),
            metrics["skew"],
            metrics["kurtosis"],
            trial_srs,
            n_trials,
        )
    return rows
