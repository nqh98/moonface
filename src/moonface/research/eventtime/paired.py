"""Paired clock-vs-event-time comparison helpers.

Both arms run the same frozen construction over different candle series. Per
exit row, this module computes additive-R drawdown statistics, runs the
existing research ladder, and derives the paired kill-rule verdict.
"""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.exits import EXIT_REGISTRY
from moonface.core.metrics import single_trade_r
from moonface.core.models import Candle
from moonface.research.entries import generate_entries
from moonface.research.ladder import (
    DSR_THRESHOLD,
    evaluate_lockbox,
    evaluate_research,
    stage1_passed,
    stage2_passed,
    stage3_dsr,
    stage4_passed,
)
from moonface.kernel.spec import HypothesisSpec

EXIT_ROWS: list[tuple[str, dict]] = [
    (name, params)
    for name, (_fn, grid) in EXIT_REGISTRY.items()
    for params in grid
]

_ASSET = {"exchange": "binanceusdm", "symbol": "BTCUSDT", "timeframe": "eventtime"}


def curve_stats(net_rs: list[float]) -> tuple[float, float]:
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for net_r in net_rs:
        cum += net_r
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
    return round(cum, 4), round(max_dd, 4)


def bundle_of(candles: list[Candle]) -> DataBundle:
    return DataBundle(candles=candles, funding=None, basis=None, feature=None)


def _net_rs(candles: list[Candle], entry_params: dict, exit_name: str,
            exit_params: dict) -> list[float]:
    entries = generate_entries("donchian_break", entry_params, bundle_of(candles))
    out: list[float] = []
    for idx, side in entries:
        result = single_trade_r(candles, idx, side, exit_name, exit_params)
        if result is None:
            continue
        out.append(result[0])
    return out


def arm_metrics(
    candles: list[Candle],
    entry_params: dict,
    exit_rows: list[tuple[str, dict]] = EXIT_ROWS,
) -> list[dict]:
    rows: list[dict] = []
    for exit_name, exit_params in exit_rows:
        net_rs = _net_rs(candles, entry_params, exit_name, exit_params)
        net_r, max_dd_r = curve_stats(net_rs)
        ratio = abs(max_dd_r) / net_r if net_r > 0 else None
        rows.append({
            "exit": exit_name,
            "params": exit_params,
            "trades": len(net_rs),
            "net_r": net_r,
            "max_dd_r": max_dd_r,
            "ratio": ratio,
        })
    return rows


def run_ladder(
    candles: list[Candle],
    entry_params: dict,
    exit_rows: list[tuple[str, dict]] = EXIT_ROWS,
    fence_fraction: float = 0.75,
    fraction: float = 0.1,
    grid_size: int = 10,
) -> dict:
    fence_index = int(len(candles) * fence_fraction)
    research = bundle_of(candles[:fence_index])
    full = bundle_of(candles)
    rows: list[dict] = []

    for exit_name, exit_params in exit_rows:
        spec = HypothesisSpec(
            domain="eventtime",
            version=1,
            asset=dict(_ASSET),
            entry={"family": "donchian_break", "params": dict(entry_params)},
            exit={"name": exit_name, "params": dict(exit_params)},
            fraction=fraction,
        )
        metrics = evaluate_research(spec, research)
        rows.append({
            "spec": spec,
            "spec_hash": f"{exit_name}:{exit_params}",
            "status": "oos_pass" if stage1_passed(metrics) and stage2_passed(metrics) else "rejected",
            "stage_results": metrics,
        })

    dsr_by_spec = stage3_dsr(rows, grid_size)
    best_dsr = max(dsr_by_spec.values()) if dsr_by_spec else None
    best_tail_mar = None
    passing_exits: list[str] = []

    for row in rows:
        dsr = dsr_by_spec.get(row["spec_hash"])
        if dsr is None or dsr < DSR_THRESHOLD:
            continue
        tail = evaluate_lockbox(row["spec"], full, fence_index)
        if not stage4_passed(tail):
            continue
        passing_exits.append(row["spec"].exit["name"])
        tail_mar = tail["tail_mar"]
        best_tail_mar = tail_mar if best_tail_mar is None else max(best_tail_mar, tail_mar)

    return {
        "ladder_pass": bool(passing_exits),
        "passing_exits": passing_exits,
        "best_dsr": best_dsr,
        "best_tail_mar": best_tail_mar,
    }


def paired_verdict(
    clock_rows: list[dict],
    dollar_rows: list[dict],
    ladder: dict,
    min_improve: float = 0.5,
) -> dict:
    by_key = {(row["exit"], str(row["params"])): row for row in clock_rows}
    paired_rows: list[dict] = []
    improved_exits: list[str] = []
    best_improvement = 0.0

    for dollar_row in dollar_rows:
        clock_row = by_key.get((dollar_row["exit"], str(dollar_row["params"])))
        improvement = 0.0
        if (
            clock_row is not None
            and clock_row.get("ratio") is not None
            and clock_row["ratio"] > 0
            and dollar_row["net_r"] > 0
            and dollar_row.get("ratio") is not None
        ):
            improvement = 1.0 - (dollar_row["ratio"] / clock_row["ratio"])
            if improvement >= min_improve:
                improved_exits.append(dollar_row["exit"])
        best_improvement = max(best_improvement, improvement)
        paired_rows.append({
            "exit": dollar_row["exit"],
            "params": dollar_row["params"],
            "clock_ratio": None if clock_row is None else clock_row["ratio"],
            "dollar_ratio": dollar_row.get("ratio"),
            "improvement": round(improvement, 4),
        })

    ladder_pass = bool(ladder.get("ladder_pass"))
    passed = best_improvement >= min_improve and ladder_pass
    return {
        "rows": paired_rows,
        "best_improvement": round(best_improvement, 4),
        "improved_exits": improved_exits,
        "ladder_pass": ladder_pass,
        "pass": passed,
        "verdict": "pass" if passed else "kill",
        "reason": "" if passed else "no_50pct_ratio_gain_or_ladder_fails",
    }
