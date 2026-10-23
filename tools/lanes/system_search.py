#!/usr/bin/env python3
"""BTC system-level strategy search CLI.

  --register : freeze PREREGISTRATION.md (grid/splits/gates) -- commit BEFORE a run.
  --run      : fetch all timeframes, split 60/20/20, run the pooled search.

Free Binance BTCUSDT OHLCV only. Paper research; promotes nothing to live. The
frozen 4h Donchian Slice-3 strategy is never read or written here."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.system_cells import (TIMEFRAMES, all_system_cells,  # noqa: E402
                                            system_cells_for)
from moonface.research.system_search import (render_result, search_system,  # noqa: E402
                                             to_leaderboard)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

MIN_BARS = 200   # a timeframe below this cannot support a credible 60/20/20 split


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_60_20_20(candles):
    """train_oos = first 80% (train+OOS); full = all bars (the last 20% holdout
    is read only inside stage 3's walk-forward)."""
    n = len(candles)
    cut = int(0.8 * n)
    return candles[:cut], candles


def _load_timeframes(symbol, start_ms, end_ms, cache_dir) -> dict:
    return {tf: fetch_perp_candles(symbol, tf, start_ms, end_ms, cache_dir)
            for tf in TIMEFRAMES}


def _write_prereg(out: Path, data: dict) -> None:
    cells = all_system_cells()
    lines = [
        "# BTC System-Level Strategy Search -- PREREGISTRATION (frozen)", "",
        f"- asof: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframes: {', '.join(TIMEFRAMES)}",
        f"- pooled n_trials (DSR): {len(cells)}",
        "- split: chronological train/OOS/sealed-holdout 60 / 20 / 20 per timeframe",
        "- gate: gross drift = DIAGNOSTIC ONLY (never kills) -> DSR>=0.95 -> "
        "ECON_BAR(PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60) "
        "-> robustness battery -> plateau",
        "- kill rule: a family failing any stage is CLOSED (no param rescue, no v2)",
        "- exits: EXIT_REGISTRY only (deploy-only trailing exit excluded; Donchian Slice-3 untouched)",
        "", "## Per-timeframe data fingerprint", "",
        "| timeframe | bars | data_sha |", "|---|---|---|",
    ]
    for tf in TIMEFRAMES:
        cs = data.get(tf, [])
        lines.append(f"| {tf} | {len(cs)} | {_sha(cs) if cs else '-'} |")
    lines += ["", "## Frozen cells", "", "| timeframe | family | swept grid |",
              "|---|---|---|"]
    seen = set()
    for c in cells:
        if c.group in seen:
            continue
        seen.add(c.group)
        grid = [x.swept for x in system_cells_for(c.timeframe) if x.group == c.group]
        lines.append(f"| {c.timeframe} | {c.family} | {grid} |")
    out.write_text("\n".join(lines) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC system-level strategy search")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--run", action="store_true")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--cache-dir", default=".backtest_cache")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = _load_timeframes(args.symbol, args.start_ms, args.end_ms, args.cache_dir)

    if args.register:
        _write_prereg(out / "PREREGISTRATION.md", data)
        print(f"registered -> {out}/PREREGISTRATION.md (commit before --run)")
        return 0

    # --run
    entries = []
    shas = {}
    for tf in TIMEFRAMES:
        cs = data[tf]
        if len(cs) < MIN_BARS:
            print(f"FEASIBILITY FAIL: {tf} has {len(cs)} bars < {MIN_BARS}")
            return 2
        train_oos, full = _split_60_20_20(cs)
        shas[tf] = _sha(cs)
        for cell in system_cells_for(tf):
            entries.append((cell, train_oos, full))
    rows = search_system(entries)
    asof = datetime.now(timezone.utc).isoformat()
    (out / "RESULT.md").write_text(render_result(rows, asof, shas))
    (out / "leaderboard.json").write_text(json.dumps(to_leaderboard(rows), indent=2))
    edge = any(r["verdict"] == "edge" for r in rows)
    print(f"verdict: {'EDGE' if edge else 'NEGATIVE'} -> {out}/RESULT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
