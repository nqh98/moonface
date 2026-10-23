#!/usr/bin/env python3
"""Characterize the standalone directional edge of one frozen MTF cell on one asset.

BTC's own counter-trend signal is the one component of the MTF basket that
survived the market-neutral (BTC-beta) hedge -- it is genuinely independent,
un-hedgeable against itself. This tool decomposes that single-path edge to show
WHERE it lives: long book vs short book, outlier dependence (expectancy with the
top winners removed), the return distribution, and the per-trade adverse/
favorable excursion path. Descriptive only -- no selection, no gate, no new cell;
it reads the already-frozen `broaden_best` cell. Free Binance OHLCV; paper."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.mtf.basket import yearly_robustness  # noqa: E402
from moonface.research.mtf.characterize import (book_stats,  # noqa: E402
                                                distribution, enriched_trades,
                                                excursion_summary,
                                                outlier_dependence)
from moonface.research.mtf.grid import (BASE_TF, BROADEN_BEST_LABEL,  # noqa: E402
                                        HEADLINE_LABEL, broaden_best_cell,
                                        headline_cell)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

_CELLS = {"headline": (headline_cell, HEADLINE_LABEL),
          "broaden_best": (broaden_best_cell, BROADEN_BEST_LABEL)}

START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000  # 2024-06-01 OOS window


def _book_row(name: str, st: dict) -> str:
    return (f"| {name} | {st['n']} | {st['longs']}/{st['shorts']} | {st['pf']} | "
            f"{st['expectancy_r']:+.3f} | {st['win_rate']:.3f} | "
            f"{st['total_r']:+.1f} | {st['max_dd_r']} | {st['mar']} | "
            f"{'YES' if st['positive'] else 'no'} |")


def _dist_line(d: dict) -> str:
    return (f"win_rate {d['win_rate']:.3f} | avg_win {d['avg_win_r']:+.3f}R | "
            f"avg_loss {d['avg_loss_r']:+.3f}R | payoff {d['payoff']:.2f} | "
            f"skew {d['skew']:+.2f} | kurt {d['kurtosis']:+.2f} | "
            f"best {d['best_r']:+.1f}R | worst {d['worst_r']:+.1f}R")


def _ol_lines(o: dict) -> list[str]:
    rows = [f"- full sample: n={o['n']}, total {o['total_r']:+.1f}R; "
            f"top {o['top5pct_count']} trades (top 5%) carry "
            f"{o['top5pct_profit_share']:.1%} of gross profit"]
    for k, v in o["ex_top_k"].items():
        rows.append(f"- drop top {k} winner(s): expectancy "
                    f"{v['expectancy_r']:+.3f}R, total {v['total_r']:+.1f}R "
                    f"({'still positive' if v['positive'] else 'GOES NEGATIVE'})")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cell", choices=sorted(_CELLS), default="broaden_best")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--out", default="experiments/mtf/CHARACTERIZE.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    cell_fn, cell_label = _CELLS[args.cell]
    cell = cell_fn()
    candles = fetch_perp_candles(args.symbol, BASE_TF, START_MS, END_MS,
                                 args.cache_dir)
    print(f"{args.symbol}: {len(candles)} {BASE_TF} bars", file=sys.stderr)
    data_sha = hashlib.sha256(f"{args.symbol}:{len(candles)}".encode()
                              ).hexdigest()[:16]

    recs = enriched_trades(candles, cell)
    recent = [r for r in recs if r["ts"] >= RECENT_MS]

    whole = book_stats(recs)
    longs = book_stats(recs, "LONG")
    shorts = book_stats(recs, "SHORT")
    whole_rc = book_stats(recent)
    longs_rc = book_stats(recent, "LONG")
    shorts_rc = book_stats(recent, "SHORT")

    dist = distribution(recs)
    dist_rc = distribution(recent)
    ol = outlier_dependence(recs)
    ol_rc = outlier_dependence(recent)
    exc = excursion_summary(recs)

    yr_rows, robust = yearly_robustness(
        [(r["ts"], r["side"], r["net_r"]) for r in recs])
    asof = datetime.now(timezone.utc).isoformat()

    out = [
        f"# MTF {args.cell} — {args.symbol} standalone edge characterization",
        "",
        f"- asof: {asof}",
        f"- data_sha: {data_sha}",
        f"- frozen cell: `{cell_label}` ({args.cell})",
        "- the one signal that survived the BTC-beta hedge (see NEUTRAL.md)",
        "- descriptive decomposition of the single faithful trade stream; no "
        "selection, no gate, no new cell",
        "",
        "## Side attribution — long book vs short book",
        "",
        "| book | n | L/S | pf | exp/trade | win_rate | totalR | maxDD_R | MAR | +ve |",
        "|---|---|---|---|---|---|---|---|---|---|",
        _book_row("WHOLE full", whole),
        _book_row("LONG full", longs),
        _book_row("SHORT full", shorts),
        _book_row("WHOLE recent", whole_rc),
        _book_row("LONG recent", longs_rc),
        _book_row("SHORT recent", shorts_rc),
        "",
        "Long book = counter-trend dip-buys inside a 4h up-regime; short book = "
        "rip-sells inside a 4h down-regime. A balanced, both-sides-profitable "
        "split is what makes this a directional L/S edge rather than disguised "
        "long-only beta.",
        "",
        "## Return distribution",
        "",
        f"- full:   {_dist_line(dist)}",
        f"- recent: {_dist_line(dist_rc)}",
        "",
        "## Outlier dependence (is the edge carried by a few trades?)",
        "",
        *_ol_lines(ol),
        "",
        f"- recent window: top {ol_rc['top5pct_count']} trades carry "
        f"{ol_rc['top5pct_profit_share']:.1%} of gross profit; "
        + "; ".join(f"drop-top-{k} {'+' if v['positive'] else 'NEG'}"
                    for k, v in ol_rc["ex_top_k"].items()),
        "",
        "## Adverse / favorable excursion (why the dip-buy needs room)",
        "",
        f"- median MAE {exc['median_mae_r']}R, median MFE {exc['median_mfe_r']}R",
        f"- median MAE of WINNERS {exc['median_mae_winners_r']}R vs LOSERS "
        f"{exc['median_mae_losers_r']}R",
        "",
        "Winners that first run materially underwater (MAE << 0) before paying "
        "are the mechanism reason a tight stop destroys this edge and a 2-day "
        "hold is load-bearing (confirms the wide-stop and hold-curve findings).",
        "",
        "## Per-year robustness",
        "",
        "| year | n | pf | exp/trade | totalR | maxDD_R | positive |",
        "|---|---|---|---|---|---|---|",
        *[f"| {r['year']} | {r['n']} | {r['pf']} | {r['expectancy_r']:+.3f} | "
          f"{r['total_r']:+.1f} | {r['max_dd_r']} | "
          f"{'YES' if r['positive'] else 'no'} |" for r in yr_rows],
        f"\nrobust_frac = {robust}",
        "",
        "## Honest reading",
        "",
        "This is a descriptive x-ray of the one edge that survived beta-hedging, "
        "not a new result. It answers: does the edge come from both sides or one; "
        "is it broad or a handful of outliers; what is the win/payoff shape; and "
        "how much heat does a winning trade take. Read the outlier-dependence and "
        "the short-book columns hardest -- an edge that needs its short book AND "
        "survives dropping its top winners is the real, deployable-shape article; "
        "one that doesn't is beta or noise in disguise. Paper only.",
        "",
    ]
    Path(args.out).write_text("\n".join(out))
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
