#!/usr/bin/env python
"""One-time BTC/USDT spot 1h fetch for the carry_measure lane.

The only network operation in the lane (SPEC experiments/carry_measure/
SPEC.md §4, approved amendment to the no-new-data rule). Uses the repo's
existing ccxt loader and cache format, then gap-checks the result. Refuses
to run if the cache file already exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from moonface.data.ohlcv import OhlcvCache, fetch_history
from moonface.research.carry_measure import (HOUR_MS, WINDOW_END_MS,
                                             WINDOW_START_MS, load_bars_1h)

CACHE_DIR = str(REPO / ".backtest_cache")
SYMBOL = "BTC/USDT"  # Binance SPOT (ccxt 'binance' class is the spot API)


def main() -> int:
    cache = OhlcvCache(CACHE_DIR)
    path = cache.path(SYMBOL, "1h")
    if Path(path).exists():
        print(f"REFUSING: {path} already exists — the one-time fetch already ran.")
        return 1
    print(f"fetching {SYMBOL} 1h spot klines -> {path}")
    fetch_history("binance", SYMBOL, "1h",
                  WINDOW_START_MS, WINDOW_END_MS + HOUR_MS, cache)
    bars = load_bars_1h(path, WINDOW_START_MS, WINDOW_END_MS)  # hard gap check
    print(f"OK: {len(bars)} hourly bars, gap check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
