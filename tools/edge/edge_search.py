#!/usr/bin/env python3
"""Run the registered price-only edge search for one timeframe; write report."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.edge_search import render_result, search, to_leaderboard
from moonface.research.edge_cells import cells_for  # Task 7
from moonface.research.universe_data import fetch_perp_candles


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Price-only edge search (one timeframe)")
    ap.add_argument("--timeframe", choices=["4h", "15m"], required=True)
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--holdout-bars", type=int, required=True)
    ap.add_argument("--cache-dir", default=".backtest_cache")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    full = fetch_perp_candles(args.symbol, args.timeframe, args.start_ms,
                              args.end_ms, args.cache_dir)
    if len(full) <= args.holdout_bars:
        print(f"FEASIBILITY FAIL: {len(full)} bars <= holdout {args.holdout_bars}")
        return 2
    train_oos = full[:-args.holdout_bars]
    cells = cells_for(args.timeframe)
    rows = search(cells, train_oos, full)
    asof = datetime.now(timezone.utc).isoformat()
    sha = hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in full).encode()
    ).hexdigest()[:16]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "RESULT.md").write_text(render_result(args.timeframe, rows, asof, sha))
    (out / "leaderboard.json").write_text(json.dumps(to_leaderboard(rows), indent=2))
    edge = any(r["verdict"] == "edge" for r in rows)
    print(f"verdict: {'EDGE' if edge else 'NEGATIVE'} -> {out}/RESULT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
