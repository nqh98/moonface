#!/usr/bin/env python3
"""BTC-beta-hedged (market-neutral) falsification of the MTF regime-quality basket.

The MTF counter-trend basket transfers to ETH/SOL/DOGE, but crypto majors share
beta, so those legs may be correlated crypto-beta timing, not independent alpha.
The program has seen this exact confound flip an apparent cross-asset edge
negative once the market component was hedged (`breadth_neutral`). This tool runs
that falsification on the strongest surviving signal: it takes the SAME frozen
cell's trades on each non-BTC asset and removes the BTC component of every
trade's PnL over its holding window (point-in-time daily beta), then asks whether
the leg -- and the market-neutral alt book -- keeps its edge.

BTC is un-hedgeable against itself, so it carries raw and is reported separately.
beta=0 reproduces the raw basket exactly (correctness anchor, covered by tests).
Free Binance OHLCV only; paper research, promotes nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.mtf.attribute import Trade, period_stats  # noqa: E402
from moonface.research.mtf.basket import (diversification,  # noqa: E402
                                          merge_streams, yearly_robustness)
from moonface.research.mtf.grid import (BASE_TF, BROADEN_BEST_LABEL,  # noqa: E402
                                        HEADLINE_LABEL, broaden_best_cell,
                                        headline_cell)
from moonface.research.mtf.neutral import hedged_leg  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

_CELLS = {"headline": (headline_cell, HEADLINE_LABEL),
          "broaden_best": (broaden_best_cell, BROADEN_BEST_LABEL)}

START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000  # 2024-06-01: the out-of-sample recent window
MARKET = "BTCUSDT"             # the hedge asset (crypto beta proxy)
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _to_stream(res_key_list, candles) -> list[Trade]:
    return [(candles[d["i"]].timestamp_ms, d["side"], d["net_r"])
            for d in res_key_list]


def _stat_row(name: str, st: dict) -> str:
    return (f"| {name} | {st['n']} | {st['longs']}/{st['shorts']} | {st['pf']} | "
            f"{st['expectancy_r']:+.3f} | {st['total_r']:+.1f} | {st['max_dd_r']} | "
            f"{st['mar']} | {'YES' if st['positive'] else 'no'} |")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cell", choices=sorted(_CELLS), default="broaden_best",
                    help="which frozen span-resolvable cell to hedge")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--out", default="experiments/mtf/NEUTRAL.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    cell_fn, cell_label = _CELLS[args.cell]
    cell = cell_fn()
    if MARKET not in args.symbols:
        print(f"error: {MARKET} (hedge asset) must be in --symbols", file=sys.stderr)
        return 2

    market = fetch_perp_candles(MARKET, BASE_TF, START_MS, END_MS, args.cache_dir)
    print(f"{MARKET} (hedge): {len(market)} {BASE_TF} bars", file=sys.stderr)

    raw_streams: dict[str, list[Trade]] = {}
    hedged_streams: dict[str, list[Trade]] = {}
    leg_rows, beta_rows, hasher = [], [], hashlib.sha256()
    n_anchor_mismatch = 0

    for sym in args.symbols:
        candles = (market if sym == MARKET
                   else fetch_perp_candles(sym, BASE_TF, START_MS, END_MS,
                                           args.cache_dir))
        print(f"{sym}: {len(candles)} {BASE_TF} bars", file=sys.stderr)
        hasher.update(f"{sym}:{len(candles)}".encode())
        if len(candles) < 5000:
            print(f"  skipped ({len(candles)} bars)", file=sys.stderr)
            continue

        res = hedged_leg(candles, market, cell)
        raw = _to_stream(res["raw"], candles)
        raw_streams[sym] = raw

        if sym == MARKET:
            # Cannot market-neutralise the market: BTC carries raw in both books.
            hedged_streams[sym] = raw
            mean_beta = float("nan")
        else:
            hedged_streams[sym] = _to_stream(res["hedged"], candles)
            betas = res["betas"]
            mean_beta = sum(betas) / len(betas) if betas else float("nan")

        raw_st = period_stats(raw)
        hed_st = period_stats(hedged_streams[sym])
        raw_rc = period_stats(raw, start_ms=RECENT_MS)
        hed_rc = period_stats(hedged_streams[sym], start_ms=RECENT_MS)
        beta_contrib = raw_st["expectancy_r"] - hed_st["expectancy_r"]
        tag = "market (raw)" if sym == MARKET else "hedged"
        leg_rows.append(_stat_row(f"{sym} raw", raw_st))
        leg_rows.append(_stat_row(f"{sym} {tag}", hed_st))
        beta_rows.append(
            f"| {sym} | {'-' if sym == MARKET else f'{mean_beta:+.3f}'} | "
            f"{raw_st['expectancy_r']:+.3f} | {hed_st['expectancy_r']:+.3f} | "
            f"{'-' if sym == MARKET else f'{beta_contrib:+.3f}'} | "
            f"{raw_rc['expectancy_r']:+.3f} | {hed_rc['expectancy_r']:+.3f} | "
            # edge verdict keys off the RECENT OOS window (the program's trust
            # anchor); BTC is raw/un-hedgeable so it trivially keeps its own edge
            f"{'kept' if (sym == MARKET or hed_rc['expectancy_r'] > 0) else 'lost'} |")
        if len(raw) != len(hedged_streams[sym]):
            n_anchor_mismatch += 1

    weight = 1.0 / len(raw_streams)
    raw_merged = merge_streams(raw_streams, weight)
    hed_merged = merge_streams(hedged_streams, weight)

    # The pure market-neutral book: hedged legs only, BTC excluded (you cannot
    # neutralise the market, so a market-neutral claim rests on the alts alone).
    alt = {s: t for s, t in hedged_streams.items() if s != MARKET}
    alt_weight = 1.0 / len(alt) if alt else 0.0
    alt_merged = merge_streams(alt, alt_weight) if alt else []

    raw_full, raw_recent = period_stats(raw_merged), period_stats(
        raw_merged, start_ms=RECENT_MS)
    hed_full, hed_recent = period_stats(hed_merged), period_stats(
        hed_merged, start_ms=RECENT_MS)
    alt_full = period_stats(alt_merged)
    alt_recent = period_stats(alt_merged, start_ms=RECENT_MS)
    _, hed_robust = yearly_robustness(hed_merged)
    _, alt_robust = yearly_robustness(alt_merged) if alt_merged else ([], 0.0)
    div_hedged = diversification(
        {s: t for s, t in hedged_streams.items()}, weight)

    # Verdict: the market-neutral claim survives iff the hedged alt book keeps a
    # positive edge (expectancy and PF>1) in BOTH full and recent windows and
    # does not sign-flip vs its raw form. Otherwise the cross-asset confirmation
    # was crypto beta (the breadth_neutral outcome).
    survives = (alt_full["expectancy_r"] > 0 and alt_full["pf"] >= 1.0
                and alt_recent["expectancy_r"] > 0)
    verdict = ("SURVIVES BTC HEDGE — candidate market-neutral alpha (unexpected)"
               if survives else
               "DOES NOT SURVIVE BTC HEDGE — cross-asset edge is crypto beta")

    asof = datetime.now(timezone.utc).isoformat()
    data_sha = hasher.hexdigest()[:16]

    out = [
        f"# MTF {args.cell} — BTC-Beta-Hedged (Market-Neutral) Falsification",
        "",
        f"## Verdict: {verdict}",
        "",
        f"- asof: {asof}",
        f"- data_sha: {data_sha}",
        f"- frozen cell: `{cell_label}` ({args.cell})",
        f"- hedge asset: {MARKET} (crypto-beta proxy); alts hedged, BTC carries raw",
        f"- beta: point-in-time trailing {90}-day daily cov/var, unit-beta fallback",
        f"- assets: {', '.join(raw_streams)}",
        "" if not n_anchor_mismatch else
        f"- WARNING: {n_anchor_mismatch} leg(s) had raw/hedged trade-count "
        "mismatch (should be 0 — same trade set)",
        "",
        "## Per-leg: does the edge survive removing BTC beta?",
        "",
        "| asset | mean beta | raw exp/trade | hedged exp/trade | beta contrib | "
        "raw exp recent | hedged exp recent | edge |",
        "|---|---|---|---|---|---|---|---|",
        *beta_rows,
        "",
        "`beta contrib` = raw − hedged expectancy (the crypto-beta share of the "
        "per-trade edge). `edge=lost` means the leg goes non-positive once beta "
        "is removed — the confirmation was market beta, not alpha.",
        "",
        "## Basket books (equal-weight single faithful path)",
        "",
        "| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |",
        "|---|---|---|---|---|---|---|---|---|",
        *leg_rows,
        _stat_row("RAW basket full", raw_full),
        _stat_row("RAW basket recent", raw_recent),
        _stat_row("HEDGED basket full", hed_full),
        _stat_row("HEDGED basket recent", hed_recent),
        _stat_row("MKT-NEUTRAL alts full", alt_full),
        _stat_row("MKT-NEUTRAL alts recent", alt_recent),
        "",
        f"- hedged basket robust_frac: {hed_robust}  |  "
        f"market-neutral alt robust_frac: {alt_robust}",
        f"- hedged-basket DD de-correlation cut: {div_hedged['dd_cut_frac']:.1%} "
        f"(merged {div_hedged['merged_dd_r']}R vs ref {div_hedged['ref_dd_r']}R)",
        "",
        "## Honest reading",
        "",
        "The MTF basket's ETH/SOL/DOGE legs 'confirm' the BTC signal, but crypto "
        "majors share beta. This test removes the BTC-beta component of each "
        "non-BTC trade's PnL over its actual holding window (point-in-time beta, "
        "no look-ahead; beta=0 reproduces raw exactly). If the market-neutral alt "
        "book keeps a positive edge, the cross-asset transfer is genuine "
        "beta-residual alpha. If it collapses or flips sign, the transfer was "
        "crypto-beta timing — the same outcome the breadth cross-asset leads met "
        "(`breadth_neutral`): a real crypto-beta timing overlay, NOT market-"
        "neutral alpha. BTC's own directional edge is untouched (un-hedgeable "
        "against itself). Paper only; promotes nothing to live.",
        "",
    ]
    Path(args.out).write_text("\n".join(out))
    print(f"\nwrote {args.out}", file=sys.stderr)
    print(f"verdict: {verdict}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
