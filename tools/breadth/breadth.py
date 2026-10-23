#!/usr/bin/env python3
"""Staged BTC breadth-thrust timing CLI (paper-only).

Frozen up front; explores on train, freezes train survivors, then opens
validate/sealed once. Breadth comes from the daily perp universe (BTC
excluded), timing a symmetric long/short BTC 4h position."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.breadth.evaluate import run_explore  # noqa: E402
from moonface.research.breadth.gates import select_survivors, validate_cell  # noqa: E402
from moonface.research.breadth.grid import all_cells  # noqa: E402
from moonface.research.breadth.signals import DAY_MS, pct_above_ma_series  # noqa: E402
from moonface.research.universe_data import (  # noqa: E402
    DailyRow,
    fetch_daily_klines,
    fetch_perp_candles,
    list_um_perp_symbols,
)
from moonface.research.xsection import build_universe  # noqa: E402

SYMBOL = "BTCUSDT"
TF = "4h"
MIN_BARS = 300
TOP_N = 20
MIN_HISTORY_DAYS = 365
VOL_DAYS = 30
REBALANCE_DAYS = 30


def split_60_20_20(candles):
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    return candles[:a], candles[a:b], candles[b:]


def universe_covers_train(daily, is_member, train, min_points: int = 50) -> bool:
    """Feasibility guard: the point-in-time universe must actually exist over the
    train window. A stale/short daily cache (e.g. a prior 3y fetch) silently
    truncates history, leaving membership empty across train/validate and
    producing a misleading 0-trade 'result'. Require >= min_points breadth
    observations inside the train span before scoring."""
    if not train:
        return False
    lo, hi = train[0].timestamp_ms, train[-1].timestamp_ms
    series = pct_above_ma_series(daily, 50, is_member)
    within = sum(1 for ts, _ in series if lo <= ts <= hi)
    return within >= min_points


def membership_fn(
    universe_daily: dict[str, list[DailyRow]],
    top_n: int,
    min_history_days: int,
    vol_days: int,
    rebalance_days: int,
) -> Callable[[str, int], bool]:
    """Point-in-time membership rebuilt on the latest rebalance boundary."""
    cache: dict[int, frozenset[str]] = {}
    rebalance_ms = rebalance_days * DAY_MS

    def members_at(ts: int) -> frozenset[str]:
        boundary = ts - (ts % rebalance_ms)
        if boundary not in cache:
            cache[boundary] = frozenset(
                build_universe(
                    universe_daily,
                    boundary,
                    top_n,
                    min_history_days,
                    vol_days,
                )
            )
        return cache[boundary]

    return lambda sym, ts: sym in members_at(ts)


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _load(args):
    btc = fetch_perp_candles(SYMBOL, TF, args.start_ms, args.end_ms, args.cache_dir)
    symbols = list_um_perp_symbols()
    daily: dict[str, list[DailyRow]] = {}
    for sym in symbols:
        rows = fetch_daily_klines(sym, args.start_ms, args.end_ms, args.cache_dir)
        if rows:
            daily[sym] = rows
    is_member = membership_fn(
        daily,
        TOP_N,
        MIN_HISTORY_DAYS,
        VOL_DAYS,
        REBALANCE_DAYS,
    )
    return btc, daily, is_member


def _register(args) -> int:
    btc = fetch_perp_candles(SYMBOL, TF, args.start_ms, args.end_ms, args.cache_dir)
    span = args.end_ms - args.start_ms
    prereg = {
        "lane": "btc_breadth_thrust_timing",
        "asof": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "timeframe": TF,
        "constants": {
            "MIN_BARS": MIN_BARS,
            "TOP_N": TOP_N,
            "MIN_HISTORY_DAYS": MIN_HISTORY_DAYS,
            "VOL_DAYS": VOL_DAYS,
            "REBALANCE_DAYS": REBALANCE_DAYS,
        },
        "cells": [cell.key for cell in all_cells()],
        "windows": {
            "train": [args.start_ms, args.start_ms + int(span * 0.6)],
            "validate": [args.start_ms + int(span * 0.6), args.start_ms + int(span * 0.8)],
            "sealed": [args.start_ms + int(span * 0.8), args.end_ms],
        },
        "gate": (
            "train practical bar + 2x/3x cost + outlier + island + DSR>=0.95 -> "
            "freeze; validate/sealed practical bar, same expectancy sign, 2x/3x cost "
            "on sealed, ECON_BAR"
        ),
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    btc, daily, is_member = _load(args)
    if len(btc) < MIN_BARS:
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2
    train = split_60_20_20(btc)[0]
    if not universe_covers_train(daily, is_member, train):
        print("FEASIBILITY FAIL: universe daily history does not cover the train "
              "window (stale/short daily cache?). Refetch daily klines for the full "
              "registration window before running.")
        return 2
    rows = run_explore(daily, train, all_cells(), is_member)
    compact = [
        {k: row[k] for k in ("key", "family", "axis", "metrics", "dsr")}
        for row in rows
    ]
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", compact)
    return 0


def _select(args) -> int:
    btc, daily, is_member = _load(args)
    train = split_60_20_20(btc)[0]
    if not universe_covers_train(daily, is_member, train):
        print("FEASIBILITY FAIL: universe daily history does not cover the train "
              "window (stale/short daily cache?). Refetch daily klines for the full "
              "registration window before running.")
        return 2
    rows = run_explore(daily, train, all_cells(), is_member)
    survivors = select_survivors(daily, train, all_cells(), rows, is_member)
    _write_json(Path(args.out_dir) / "frozen_candidates.json", [c.key for c in survivors])
    return 0


def _validate(args) -> int:
    frozen_path = Path(args.out_dir) / "frozen_candidates.json"
    if not frozen_path.exists():
        print("no frozen_candidates.json; run --select first")
        return 3

    frozen_keys = set(json.loads(frozen_path.read_text()))
    btc, daily, is_member = _load(args)
    _, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        print("FEASIBILITY FAIL: universe daily history does not cover the validate "
              "window (stale/short daily cache?). Refetch daily klines for the full "
              "registration window before running.")
        return 2
    cells = [cell for cell in all_cells() if cell.key in frozen_keys]
    rows = [validate_cell(daily, val, seal, cell, is_member) for cell in cells]
    verdict = (
        "paper_candidate"
        if any(row["verdict"] == "paper_candidate" for row in rows)
        else "negative"
    )

    _write_json(
        Path(args.out_dir) / "RESULT.json",
        {
            "lane": "btc_breadth_thrust_timing",
            "asof": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "rows": rows,
            "btc_sha": _sha(btc),
        },
    )

    lines = [
        "# BTC Breadth-Thrust Timing",
        "",
        f"## Verdict: {'PAPER CANDIDATE (paper-only)' if verdict == 'paper_candidate' else 'NEGATIVE'}",
        "",
        "| cell | val_R | val_exp | seal_R | seal_exp | econ | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        val = row["validate"]
        seal_row = row["sealed"]
        lines.append(
            f"| {row['key']} | {val['total_r']:.3f} | {val['expectancy_r']:.3f} | "
            f"{seal_row['total_r']:.3f} | {seal_row['expectancy_r']:.3f} | "
            f"{'Y' if row['econ_passed'] else 'n'} | {row['verdict']} |"
        )
    if not rows:
        lines.append("| (no train survivors) | - | - | - | - | - | negative |")
    lines.extend(["", "Paper-only. A negative outcome is expected and valid.", ""])
    (Path(args.out_dir) / "FINDINGS.md").write_text("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true")
    group.add_argument("--explore", action="store_true")
    group.add_argument("--select", action="store_true")
    group.add_argument("--validate", action="store_true")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", default="experiments/breadth")
    return p


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    if args.register:
        return _register(args)
    if args.explore:
        return _explore(args)
    if args.select:
        return _select(args)
    return _validate(args)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
