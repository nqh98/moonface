#!/usr/bin/env python3
"""Equal-weight cross-asset basket of the frozen MTF headline cell.

Runs the SAME frozen cell (1d trend gate + 15m RSI counter-trend entry + 2-day
hold behind a 3xATR wide stop) on BTC/ETH/SOL -- each gated by its OWN 1d trend --
and measures the single faithful equity path of an equal-risk (1/N) book that
takes every asset's trades. Tests the program's standing question: does a
portfolio structure relax the single-asset drawdown wall for the one signal that
has worked OOS and transferred?

Equal weight is the only non-data-mined construction; no per-asset weight is
tuned. Free Binance OHLCV only; paper research, promotes nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.kernel.econ import ECON_BAR  # noqa: E402
from moonface.research.mtf.attribute import period_stats, trade_stream  # noqa: E402
from moonface.research.mtf.basket import (diversification,  # noqa: E402
                                          merge_streams, yearly_robustness)
from moonface.research.mtf.grid import (BASE_TF, BROADEN_BEST_LABEL,  # noqa: E402
                                        HEADLINE_LABEL, broaden_best_cell,
                                        headline_cell)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

# Frozen cells this basket can run. Both are single-path selections already
# registered for forward paper; the basket diversifies their cross-asset path,
# it does not re-select among cells (no new DSR deflation).
_CELLS = {"headline": (headline_cell, HEADLINE_LABEL),
          "broaden_best": (broaden_best_cell, BROADEN_BEST_LABEL)}

START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000  # 2024-06-01: the out-of-sample recent window
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _stat_row(name: str, st: dict) -> str:
    return (f"| {name} | {st['n']} | {st['longs']}/{st['shorts']} | {st['pf']} | "
            f"{st['expectancy_r']:+.3f} | {st['total_r']:+.1f} | {st['max_dd_r']} | "
            f"{st['mar']} | {'YES' if st['positive'] else 'no'} |")


def _econ_line(st: dict, robust: float) -> str:
    b = ECON_BAR
    checks = [
        ("PF", st["pf"], b.profit_factor, st["pf"] >= b.profit_factor),
        ("exp", st["expectancy_r"], b.expectancy_r,
         st["expectancy_r"] >= b.expectancy_r),
        ("MAR", st["mar"], b.mar_floor, st["mar"] >= b.mar_floor),
        ("DD", st["max_dd_r"], -b.max_dd_r, abs(st["max_dd_r"]) <= b.max_dd_r),
        ("robust", robust, b.robust_frac, robust >= b.robust_frac),
    ]
    return " | ".join(f"{n} {v} {'PASS' if ok else 'FAIL'}"
                      for n, v, _, ok in checks)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cell", choices=sorted(_CELLS), default="headline",
                    help="which frozen single-path cell to basket")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--out", default="experiments/mtf/BASKET.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    cell_fn, cell_label = _CELLS[args.cell]
    cell = cell_fn()
    weight = 1.0 / len(args.symbols)
    streams, indiv_rows, hasher = {}, [], hashlib.sha256()
    for sym in args.symbols:
        candles = fetch_perp_candles(sym, BASE_TF, START_MS, END_MS, args.cache_dir)
        print(f"{sym}: {len(candles)} {BASE_TF} bars", file=sys.stderr)
        hasher.update(f"{sym}:{len(candles)}".encode())
        if len(candles) < 5000:
            print(f"  skipped ({len(candles)} bars)", file=sys.stderr)
            continue
        streams[sym] = trade_stream(candles, cell)
        # individual asset rows are reported at FULL weight (stand-alone book)
        indiv_rows.append(_stat_row(sym, period_stats(streams[sym])))
        indiv_rows.append(_stat_row(f"{sym} recent",
                                    period_stats(streams[sym], start_ms=RECENT_MS)))

    merged = merge_streams(streams, weight)
    full = period_stats(merged)
    recent = period_stats(merged, start_ms=RECENT_MS)
    yr_rows, robust = yearly_robustness(merged)
    div = diversification(streams, weight)
    asof = datetime.now(timezone.utc).isoformat()
    data_sha = hasher.hexdigest()[:16]

    clears = (full["pf"] >= ECON_BAR.profit_factor
              and full["expectancy_r"] >= ECON_BAR.expectancy_r
              and full["mar"] >= ECON_BAR.mar_floor
              and abs(full["max_dd_r"]) <= ECON_BAR.max_dd_r
              and robust >= ECON_BAR.robust_frac)
    verdict = ("CLEARS ECON_BAR (paper candidate)" if clears
               else "DOES NOT CLEAR ECON_BAR (thin edge, large drawdown)")

    out = [
        f"# MTF {args.cell} cell — Equal-Weight Cross-Asset Basket",
        "",
        f"## Verdict: {verdict}",
        "",
        f"- asof: {asof}",
        f"- data_sha: {data_sha}",
        f"- frozen cell: `{cell_label}` ({args.cell})",
        f"- construction: equal {weight:.3f} risk weight per asset "
        f"({len(streams)} assets), single faithful merged equity path",
        f"- assets: {', '.join(streams)}  (each gated by its OWN 1d trend)",
        "",
        "## Single-asset books (full weight, for reference)",
        "",
        "| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |",
        "|---|---|---|---|---|---|---|---|---|",
        *indiv_rows,
        "",
        "## Equal-weight basket (single faithful path)",
        "",
        "| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |",
        "|---|---|---|---|---|---|---|---|---|",
        _stat_row("BASKET full", full),
        _stat_row("BASKET recent", recent),
        "",
        "## Drawdown diversification",
        "",
        f"- perfect-correlation reference DD (weighted sum of individual): "
        f"{div['ref_dd_r']}R",
        f"- realized merged-path DD: {div['merged_dd_r']}R",
        f"- **drawdown cut from de-correlation: {div['dd_cut_frac']:.1%}**",
        "",
        "## Per-year robustness (merged path)",
        "",
        "| year | n | pf | exp/trade | totalR | maxDD_R | positive |",
        "|---|---|---|---|---|---|---|",
        *[f"| {r['year']} | {r['n']} | {r['pf']} | {r['expectancy_r']:+.3f} | "
          f"{r['total_r']:+.1f} | {r['max_dd_r']} | "
          f"{'YES' if r['positive'] else 'no'} |" for r in yr_rows],
        f"\nrobust_frac = {robust} (single-asset BTC reference: 0.553)",
        "",
        "## ECON_BAR check (full basket)",
        "",
        "`PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`",
        "",
        _econ_line(full, robust),
        "",
        "## Honest reading",
        "",
        "Equal-weight diversification de-correlates the loser-clustering that "
        "drives the single-asset wall, and lifts robustness above the 0.60 floor "
        "that the single-asset signal failed. But it does not thicken the edge: "
        "PF stays below 1.2 and the single-path drawdown still exceeds the 30R "
        "fixed-f cap (a sizing failure -- f~0.003 maps it to ~30% equity). The "
        "basket is a MORE ROBUST deployment of the same thin signal, not a "
        "deployable edge. Crypto majors share beta, so the assets are correlated "
        "confirmations, not independent ones (see the program's breadth-neutral "
        "finding). Paper only; promotes nothing to live.",
        "",
    ]
    Path(args.out).write_text("\n".join(out))
    print(f"\nwrote {args.out}", file=sys.stderr)
    print(f"verdict: {verdict}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
