"""Cache-only pool loading and the aligned cross-sectional return matrix.

Correlation topology needs returns and nothing else, so this lane never
touches OI, funding, or bookdepth -- that is the entire fetch cost the
microscope run paid (~8 min/asset) and this one does not."""
from __future__ import annotations

import math
import os

from moonface.foundation.bundle import DataBundle
from moonface.foundation.data import OhlcvCache

# The 16 frozen drift_screen assets plus BTCUSDT -- the universe the 1838
# Donchian events were generated on. Deliberately no ETH, no SOL (spec 3.1).
UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT", "BTCUSDT"]

TIMEFRAME = "4h"


def load_pool_cache_only(cache_dir: str,
                         symbols: list[str] = UNIVERSE
                         ) -> dict[str, DataBundle]:
    """{symbol: DataBundle} from the CSV cache only -- never fetches.

    Raises on a missing symbol instead of skipping it. The microscope's first
    run silently collapsed to BTC-only because its reader returned [] for
    missing files, which made every event UNLABELED; a loud failure is the fix."""
    cache = OhlcvCache(cache_dir)
    pool: dict[str, DataBundle] = {}
    for sym in symbols:
        candles = cache.load(sym, TIMEFRAME)
        if not candles:
            raise FileNotFoundError(
                f"no cached {TIMEFRAME} candles for {sym} at "
                f"{os.path.join(cache_dir, f'{sym}_{TIMEFRAME}.csv')}")
        pool[sym] = DataBundle(candles=candles)
    return pool


def build_grid(pool: dict[str, DataBundle]) -> list[int]:
    """Sorted union of bar-open timestamps -- the shared axis, matching
    microscope.features.build_matrix so labels index the same way."""
    ts: set[int] = set()
    for bundle in pool.values():
        ts.update(c.timestamp_ms for c in bundle.candles)
    return sorted(ts)


def log_return_matrix(pool: dict[str, DataBundle],
                      timestamps: list[int]) -> dict[str, list[float | None]]:
    """{symbol: [log return at each grid bar]}, None where the asset has no
    bar or no adjacent prior bar. Adjacency is on the asset's own series, so
    a hole in one asset never fabricates a return across it."""
    index = {ts: i for i, ts in enumerate(timestamps)}
    out: dict[str, list[float | None]] = {}
    for sym, bundle in pool.items():
        series: list[float | None] = [None] * len(timestamps)
        candles = bundle.candles
        for k in range(1, len(candles)):
            prev, cur = candles[k - 1], candles[k]
            if prev.close <= 0 or cur.close <= 0:
                continue
            t = index[cur.timestamp_ms]
            if index[prev.timestamp_ms] != t - 1:
                continue          # gap on the shared axis; not a 1-bar return
            series[t] = math.log(cur.close / prev.close)
        out[sym] = series
    return out
