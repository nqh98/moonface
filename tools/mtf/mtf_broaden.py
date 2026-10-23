#!/usr/bin/env python3
"""Broadened BTC multi-timeframe L/S search (15m base, HTF bias).

Broadens the frozen 24-cell MTF grid along NEW structural axes -- regime
DEFINITION (trend sign / momentum sign / regime QUALITY that skips chop) and hold
horizon (1d / 2d) -- to ask whether any structurally-different cell BEATS the
frozen headline cell or clears the deployable ECON_BAR. Same honest 3-stage
diagnostic: gross Z (diagnostic) -> DSR deflated by the full new n_trials (72) ->
econ walk-forward for every cell. The frozen all_cells/headline spec and the 4h
Donchian Slice-3 strategy are never touched. Free Binance BTCUSDT OHLCV; paper
research, promotes nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.mtf.evaluate import (render_diagnostic,  # noqa: E402
                                            search_diagnostic)
from moonface.research.mtf.grid import BASE_TF, broadened_cells  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

SYMBOL = "BTCUSDT"
START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
MIN_BARS = 2000


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--out", default="experiments/mtf/BROADEN.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    candles = fetch_perp_candles(SYMBOL, BASE_TF, START_MS, END_MS, args.cache_dir)
    if len(candles) < MIN_BARS:
        print(f"only {len(candles)} {BASE_TF} bars (<{MIN_BARS}); aborting",
              file=sys.stderr)
        return 1
    print(f"{len(candles)} {BASE_TF} bars", file=sys.stderr)

    cells = broadened_cells()
    cut = int(0.8 * len(candles))
    train_oos, full = candles[:cut], candles
    print(f"{len(cells)} cells; running diagnostic...", file=sys.stderr)
    rows = search_diagnostic(cells, train_oos, full)

    asof = datetime.now(timezone.utc).isoformat()
    report = render_diagnostic(rows, asof, _sha(candles), len(cells))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"\nwrote {out}", file=sys.stderr)
    # echo the top few cells to stderr for a quick read
    for r in rows[:6]:
        m = r["stage3"]["metrics"]
        print(f"  {r['label']}: dsr={r['stage2']['dsr']:.3f} "
              f"pf={m.get('profit_factor')} mar={m.get('mar')} "
              f"dd={m.get('max_dd_r')} robust={m.get('robust_frac')} "
              f"econ={'PASS' if r['econ_pass'] else '-'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
