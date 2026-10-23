#!/usr/bin/env python3
"""Stage-2: backfill full-history OHLCV + funding for the swing universe.

Survivorship-clean: list_um_perp_symbols walks the Vision listing (includes
delisted symbols). Top-N by quote volume over a recent ranking window.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.universe_data import (
    fetch_daily_klines, fetch_funding_rates, fetch_perp_candles,
    list_um_perp_symbols,
)


def rank_symbols(daily_rows_by_symbol: dict[str, list], min_rows: int = 365) -> list[str]:
    """Order symbols by total quote volume (desc), dropping those with fewer
    than `min_rows` daily bars (survivorship/liquidity floor)."""
    scored: list[tuple[float, str]] = []
    for sym, rows in daily_rows_by_symbol.items():
        if len(rows) < min_rows:
            continue
        vol = sum(r.quote_volume for r in rows)
        scored.append((vol, sym))
    scored.sort(reverse=True)
    return [sym for _, sym in scored]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill swing universe history")
    ap.add_argument("--cache-dir", default="cache/swing")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--interval", default="4h", choices=["4h", "1d"])
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--rank-days", type=int, default=60)
    args = ap.parse_args(argv)

    symbols = list_um_perp_symbols()
    rank_lo = args.end_ms - args.rank_days * 86_400_000
    rows_by_sym: dict[str, list] = {}
    for sym in symbols:
        rows = fetch_daily_klines(sym, rank_lo, args.end_ms, args.cache_dir)
        if rows:
            rows_by_sym[sym] = rows
    ranked = rank_symbols(rows_by_sym)[: args.top_n]
    print(f"universe (top {args.top_n}): {', '.join(ranked)}")
    for sym in ranked:
        fetch_perp_candles(sym, args.interval, args.start_ms, args.end_ms, args.cache_dir)
        fetch_funding_rates(sym, args.start_ms, args.end_ms, args.cache_dir)
    print(f"backfill complete for {len(ranked)} symbols -> {args.cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
