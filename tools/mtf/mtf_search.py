#!/usr/bin/env python3
"""BTC multi-timeframe confluence L/S signal search CLI.

  --run : fetch the base 15m series, derive HTF bias by resampling, split 80/20,
          run the frozen 3-stage gate over the MTF cell grid, render the report.

A higher timeframe sets the directional bias; the 15m trigger fires only with
that bias. Free Binance BTCUSDT OHLCV only. Paper research; promotes nothing to
live. The frozen 4h Donchian Slice-3 strategy is never read or written here."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.mtf.evaluate import (render_diagnostic,  # noqa: E402
                                            search_diagnostic)
from moonface.research.mtf.grid import BASE_TF, all_cells  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

SYMBOL = "BTCUSDT"
START_MS = 1_577_836_800_000   # 2020-01-01 UTC (matches the 1h/4h caches)
END_MS = 1_782_000_000_000
MIN_BARS = 2000                # below this an 80/20 split is not credible


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_train_full(candles):
    """train_oos = first 80%; full = all bars (last 20% holdout read only inside
    stage 3's walk-forward)."""
    cut = int(0.8 * len(candles))
    return candles[:cut], candles


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="fetch + run the search")
    ap.add_argument("--cache-dir", default=".backtest_cache")
    ap.add_argument("--out", default="experiments/mtf/RESULT.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    candles = fetch_perp_candles(SYMBOL, BASE_TF, START_MS, END_MS, args.cache_dir)
    if len(candles) < MIN_BARS:
        print(f"only {len(candles)} {BASE_TF} bars (<{MIN_BARS}); aborting",
              file=sys.stderr)
        return 1
    print(f"{len(candles)} {BASE_TF} bars "
          f"[{candles[0].timestamp_ms}..{candles[-1].timestamp_ms}]",
          file=sys.stderr)

    cells = all_cells()
    train_oos, full = _split_train_full(candles)
    rows = search_diagnostic(cells, train_oos, full)

    asof = datetime.now(timezone.utc).isoformat()
    report = render_diagnostic(rows, asof, _sha(candles), len(cells))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
