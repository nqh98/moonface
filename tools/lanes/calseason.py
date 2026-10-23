#!/usr/bin/env python
"""Calseason calendar-seasonality one-touch study CLI."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.universe_data import fetch_perp_candles
from moonface.research.calseason import (CELLS, MIN_ASSETS, MIN_BREADTH,
                                         MIN_RETURNS, ABS_STOUFFER_GATE,
                                         calseason_verdict, cell_returns,
                                         pooled_cell)
from moonface.features.oi_features import asset_stats
from tools.lanes.oibuild_study import candidates_from_caches

_DAY_MS = 86_400_000

DESIGN = {
    "interval": "4h",
    "cells": list(CELLS),
    "n_confirm": 16,
    "min_assets": MIN_ASSETS,
    "min_returns": MIN_RETURNS,
    "min_breadth": MIN_BREADTH,
    "abs_stouffer_gate": ABS_STOUFFER_GATE,
    "discovery": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "window_days": 730,
    "top_k_candidates": 24,
    "vol_days": 30,
    "min_history_days": 365,
}


def resolve_candidates(cache_dir: str, window_start: int) -> list[str]:
    return candidates_from_caches(
        cache_dir, window_start, exclude=set(DESIGN["discovery"]),
        top_k=DESIGN["top_k_candidates"], vol_days=DESIGN["vol_days"],
        min_history_days=DESIGN["min_history_days"])


def cmd_register(out_dir: Path, candidates: list[str],
                 now_ms: int | None = None) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    reg = dict(DESIGN)
    reg["end_ms"] = now
    reg["start_ms"] = now - DESIGN["window_days"] * _DAY_MS
    reg["candidates"] = candidates
    reg["registered_utc"] = dt.datetime.fromtimestamp(
        now / 1000, dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} ({len(candidates)} candidates frozen)")


def _split_stats(candles, cell):
    mid = len(candles) // 2
    first = cell_returns(candles[:mid + 1])[cell]
    second = cell_returns(candles[mid:])[cell]
    return {"first": asset_stats(first), "second": asset_stats(second)}


def run_analysis(cfg: dict, fetch_candles, out_dir: Path) -> dict:
    verdict_path = out_dir / "verdict.json"
    if verdict_path.exists():
        sys.exit(f"{verdict_path} already exists; the analysis is one-touch")
    accepted = []
    skipped = []
    for sym in cfg["candidates"]:
        if len(accepted) >= cfg["n_confirm"]:
            break
        candles = fetch_candles(sym, cfg["start_ms"], cfg["end_ms"])
        if len(candles) < 2:
            skipped.append(sym)
            continue
        accepted.append({"sym": sym, "candles": candles})

    cell_stats = {name: [] for name in CELLS}
    per_asset = []
    for a in accepted:
        returns = cell_returns(a["candles"])
        row = {"sym": a["sym"]}
        for name in CELLS:
            s = asset_stats(returns[name])
            row[name] = s
            cell_stats[name].append(s)
        per_asset.append(row)

    halves = {name: {"first": [], "second": []} for name in CELLS}
    for a in accepted:
        for name in CELLS:
            split = _split_stats(a["candles"], name)
            halves[name]["first"].append(split["first"])
            halves[name]["second"].append(split["second"])
    half_summary = {
        name: {
            "first": pooled_cell(halves[name]["first"]),
            "second": pooled_cell(halves[name]["second"]),
        }
        for name in CELLS
    }
    verdict = calseason_verdict(cell_stats, half_summary)
    out = {
        **verdict,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "assets": per_asset,
        "skipped": skipped,
        "halves": half_summary,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(json.dumps(out, indent=2))
    (out_dir / "report.md").write_text(_render(cfg, out))
    return out


def _render(cfg: dict, v: dict) -> str:
    lines = [
        "# Calseason calendar seasonality verdict",
        "",
        f"- generated: {v['generated_utc']}",
        f"- **status: {v['status']}** - {v['reason']}",
        f"- winner: {v['winner'] if v['winner'] else '-'}",
        f"- accepted assets: {len(v['assets'])} (skipped: {len(v['skipped'])})",
        "",
        "| cell | m | pooled mean | Stouffer Z | |Z| | same-sign | stable | clears |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for name, row in v["cells"].items():
        lines.append(
            f"| {name} | {row['m']} | {row['pooled_mean']:.8f} | "
            f"{row['stouffer_z']:.3f} | {row['abs_stouffer_z']:.3f} | "
            f"{row['same_sign']} | {_b(row['stable_halves'])} | "
            f"{_b(row['clears_gate'])} |")
    lines += ["", "## Time Halves", "", "```json",
              json.dumps(v["halves"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def _b(v: bool) -> str:
    return "PASS" if v else "fail"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/calseason")
    p.add_argument("--cache-dir", default=".backtest_cache")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("register", help="freeze window, universe, and cells")
    sub.add_parser("run", help="one-touch OHLCV-only analysis")
    args = p.parse_args()
    out_dir = Path(args.out)
    if args.command == "register":
        now = int(time.time() * 1000)
        candidates = resolve_candidates(
            args.cache_dir, now - DESIGN["window_days"] * _DAY_MS)
        cmd_register(out_dir, candidates, now_ms=now)
        return
    reg_path = out_dir / "registration.json"
    if not reg_path.exists():
        sys.exit("no registration; run `register` first")
    cfg = json.loads(reg_path.read_text())

    def fetch_candles(sym, start, end):
        return fetch_perp_candles(sym, cfg["interval"], start, end,
                                  args.cache_dir)

    v = run_analysis(cfg, fetch_candles, out_dir)
    print(f"[{v['status']}] {v['reason']}")
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
