#!/usr/bin/env python
"""Macro event-window study CLI (FOMC/CPI event-time conditioning on BTC).

`register` freezes the design, calendars, and data window BEFORE any data
contact; `run` is one-touch: fetch BTCUSDT 1h perp candles, score the 4
frozen cells, write verdict.json + report.md, and refuse a second run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.core.metrics import COST_FRACTION
from moonface.research.macro_event import (ALPHA_BONFERRONI, BOOT_SEED, CELLS,
                                           CPI_DATES, FOMC_DATES, MIN_EVENTS,
                                           N_BOOT, WINDOW_MS, cell_returns,
                                           cell_summary, event_ts_ms,
                                           macro_event_verdict)
from moonface.research.universe_data import fetch_perp_candles

_DAY_MS = 86_400_000

DESIGN = {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "cells": list(CELLS),
    "direction": "long",
    "window_ms": WINDOW_MS,
    "cost_round_trip": COST_FRACTION,
    "min_events": MIN_EVENTS,
    "n_boot": N_BOOT,
    "boot_seed": BOOT_SEED,
    "alpha_bonferroni": ALPHA_BONFERRONI,
    "n_fomc": len(FOMC_DATES),
    "n_cpi": len(CPI_DATES),
    "events_start_utc": "2022-01-01",
}


def cmd_register(out_dir: Path, now_ms: int | None = None) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    reg = dict(DESIGN)
    reg["end_ms"] = now
    reg["start_ms"] = int(dt.datetime(2022, 1, 1,
                                      tzinfo=dt.timezone.utc).timestamp() * 1000)
    reg["fomc_ts_ms"] = event_ts_ms("fomc")
    reg["cpi_ts_ms"] = event_ts_ms("cpi")
    reg["registered_utc"] = dt.datetime.fromtimestamp(
        now / 1000, dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} ({reg['n_fomc']} FOMC + {reg['n_cpi']} CPI "
          "events frozen)")


def run_analysis(cfg: dict, fetch_candles, out_dir: Path) -> dict:
    verdict_path = out_dir / "verdict.json"
    if verdict_path.exists():
        sys.exit(f"{verdict_path} already exists; the analysis is one-touch")
    # 48h margin so the first pre-window and last post-window are computable.
    candles = fetch_candles(cfg["symbol"],
                            cfg["start_ms"] - 2 * _DAY_MS,
                            cfg["end_ms"])
    cells = {}
    for name in CELLS:
        event_type, window = name.split("_", 1)
        returns = cell_returns(candles, event_type, window)
        summary = cell_summary(returns)
        summary["returns"] = returns
        cells[name] = summary
    verdict = macro_event_verdict(cells)
    out = {
        **verdict,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "candles": len(candles),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(json.dumps(out, indent=2))
    (out_dir / "report.md").write_text(_render(cfg, out))
    return out


def _render(cfg: dict, v: dict) -> str:
    lines = [
        "# Macro event-window study verdict (FOMC/CPI event time, BTC)",
        "",
        f"- generated: {v['generated_utc']}",
        f"- **status: {v['status']}** - {v['reason']}",
        f"- winner: {v['winner'] if v['winner'] else '-'}",
        f"- candles: {v['candles']} ({cfg['symbol']} {cfg['interval']})",
        f"- gate: net mean > 0, p_le0 < {cfg['alpha_bonferroni']}, "
        f"halves sign-consistent, n >= {cfg['min_events']}; "
        f"cost {cfg['cost_round_trip']} round trip per event",
        "",
        "| cell | n | net mean | p(mean<=0) | 1st half | 2nd half | halves | clears |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for name in CELLS:
        row = v["cells"][name]
        lines.append(
            f"| {name} | {row['n']} | {row['net_mean']:.6f} | "
            f"{row['p_le0']:.4f} | {row['first_half_mean']:.6f} | "
            f"{row['second_half_mean']:.6f} | {_b(row['halves_sign_ok'])} | "
            f"{_b(row['clears_gate'])} |")
    return "\n".join(lines) + "\n"


def _b(v: bool) -> str:
    return "PASS" if v else "fail"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/macro_event")
    p.add_argument("--cache-dir", default=".backtest_cache")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("register", help="freeze design, calendars, and window")
    sub.add_parser("run", help="one-touch event-window analysis")
    args = p.parse_args()
    out_dir = Path(args.out)
    if args.command == "register":
        cmd_register(out_dir)
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
