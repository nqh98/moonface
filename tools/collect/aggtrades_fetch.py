#!/usr/bin/env python
"""Data acquisition only: build/extend the per-second aggTrades cache and
export the frozen analysis window. No features, no returns, no analysis."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.data.aggtrades import export_window, fetch_aggsec_history


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--export", help="write the [start,end) slice of the cache"
                                    " to this CSV path and exit")
    args = p.parse_args()
    if args.export:
        n = export_window(args.symbol, args.start_ms, args.end_ms,
                          args.cache_dir, Path(args.export))
        print(f"exported {n} rows -> {args.export}")
        return
    stats = fetch_aggsec_history(args.symbol, args.start_ms, args.end_ms,
                                 args.cache_dir)
    print(f"fetched {stats['fetched_days']} days"
          f" (missing: {stats['missing_days']}) -> {stats['cache']}")


if __name__ == "__main__":
    main()
