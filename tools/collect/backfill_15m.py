#!/usr/bin/env python3
"""Backfill BTCUSDT 15m OHLCV into the standard cache for the day-15m search.

Feasibility-gated: exits 2 if the fetched history is too short to support an
OOS + sealed-holdout split (the day agent must then stop, NOT fall back to 1h)."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.universe_data import fetch_perp_candles

MIN_15M_ROWS = 20_000  # ~208 days of 15m bars: enough for train+OOS+holdout


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Backfill BTCUSDT 15m OHLCV")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="15m")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--cache-dir", default=".backtest_cache")
    args = ap.parse_args(argv)

    candles = fetch_perp_candles(
        args.symbol, args.interval, args.start_ms, args.end_ms, args.cache_dir
    )
    rows = len(candles)
    if rows == 0:
        print("FEASIBILITY FAIL: 0 rows fetched")
        return 2
    span_days = (candles[-1].timestamp_ms - candles[0].timestamp_ms) / 86_400_000
    digest = hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]
    print(
        f"rows={rows} span_days={span_days:.1f} "
        f"first={_iso(candles[0].timestamp_ms)} "
        f"last={_iso(candles[-1].timestamp_ms)} sha={digest}"
    )
    if rows < MIN_15M_ROWS:
        print(
            f"FEASIBILITY FAIL: rows {rows} < MIN_15M_ROWS {MIN_15M_ROWS}"
        )
        return 2
    print("FEASIBILITY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
