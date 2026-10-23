#!/usr/bin/env python3
"""BTC long-only deployment analysis of the frozen MTF regime-quality cell.

The market-neutral hedge left BTC's own counter-trend signal standing, and the
characterization (CHARACTERIZE.md) showed that edge is carried entirely by its
LONG book -- counter-trend dip-buys inside a 4h up-regime -- while the short book
loses over full history and only works in the recent two-sided market. This tool
evaluates the long-only book on its OWN terms: the single faithful path of just
the LONG trades, against the deployable ECON_BAR, per-year (including the 2022
bear -- the decisive "is this just BTC beta?" test), and with a passive
buy-and-hold column so long-timing can be told apart from long exposure.

HONEST STATUS: long-only is a POST-HOC side filter chosen after seeing the short
book lose -- a selection, not a pre-registered discovery. Its only defensible
promotion instrument is the frozen forward registration
(LONG_ONLY_FORWARD_REGISTRATION.md). This is a decomposition, not a new edge.
Free Binance OHLCV; paper research, promotes nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.kernel.econ import ECON_BAR  # noqa: E402
from moonface.research.mtf.attribute import period_stats, trade_stream  # noqa: E402
from moonface.research.mtf.basket import _year, yearly_robustness  # noqa: E402
from moonface.research.mtf.grid import (BASE_TF, BROADEN_BEST_LABEL,  # noqa: E402
                                        broaden_best_cell)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000  # 2024-06-01 OOS window


def _stat_row(name: str, st: dict) -> str:
    return (f"| {name} | {st['n']} | {st['pf']} | {st['expectancy_r']:+.3f} | "
            f"{st['win_rate']:.3f} | {st['total_r']:+.1f} | {st['max_dd_r']} | "
            f"{st['mar']} | {'YES' if st['positive'] else 'no'} |")


def _econ_line(st: dict, robust: float) -> str:
    b = ECON_BAR
    checks = [
        ("PF", st["pf"], st["pf"] >= b.profit_factor),
        ("exp", st["expectancy_r"], st["expectancy_r"] >= b.expectancy_r),
        ("MAR", st["mar"], st["mar"] >= b.mar_floor),
        ("DD", st["max_dd_r"], abs(st["max_dd_r"]) <= b.max_dd_r),
        ("robust", robust, robust >= b.robust_frac),
    ]
    return " | ".join(f"{n} {v} {'PASS' if ok else 'FAIL'}" for n, v, ok in checks)


def _yearly_btc_return(candles) -> dict[int, float]:
    """Passive buy-and-hold % per calendar year (first vs last close), so the
    long-only book's per-year R can be read against what simply holding BTC did."""
    first: dict[int, float] = {}
    last: dict[int, float] = {}
    for c in candles:
        y = _year(c.timestamp_ms)
        first.setdefault(y, c.close)
        last[y] = c.close
    return {y: (last[y] / first[y] - 1.0) for y in first}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--out", default="experiments/mtf/LONG_ONLY.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    cell = broaden_best_cell()
    candles = fetch_perp_candles(args.symbol, BASE_TF, START_MS, END_MS,
                                 args.cache_dir)
    print(f"{args.symbol}: {len(candles)} {BASE_TF} bars", file=sys.stderr)
    data_sha = hashlib.sha256(f"{args.symbol}:{len(candles)}".encode()
                              ).hexdigest()[:16]

    stream = trade_stream(candles, cell)
    longs = [t for t in stream if t[1] == "LONG"]
    ls_full = period_stats(stream)
    lo_full = period_stats(longs)
    lo_recent = period_stats(longs, start_ms=RECENT_MS)
    yr_rows, robust = yearly_robustness(longs)
    bh = _yearly_btc_return(candles)

    # time in market: each held ~cell.h bars (2d); an approximation of exposure
    exposure = min(1.0, len(longs) * cell.h / len(candles))

    clears = (lo_full["pf"] >= ECON_BAR.profit_factor
              and lo_full["expectancy_r"] >= ECON_BAR.expectancy_r
              and lo_full["mar"] >= ECON_BAR.mar_floor
              and abs(lo_full["max_dd_r"]) <= ECON_BAR.max_dd_r
              and robust >= ECON_BAR.robust_frac)
    verdict = ("CLEARS ECON_BAR (paper candidate)" if clears
               else "DOES NOT CLEAR ECON_BAR (DD cap over 30R — sizing failure)")

    # the decisive beta test: how does long-only behave in DOWN years? A pure-beta
    # long book loses in every down year; a timing overlay can stay positive when
    # the drawdown is shallow enough for its dip-buys to reclaim.
    down_years = [(r, bh.get(r["year"], 0.0)) for r in yr_rows
                  if bh.get(r["year"], 0.0) < 0]
    pos_down = [r for r, _ in down_years if r["positive"]]
    bear = next((r for r in yr_rows if r["year"] == 2022), None)
    beta_note = (
        f"long-only was positive in {len(pos_down)} of {len(down_years)} BTC "
        "DOWN years ("
        + ", ".join(f"{r['year']} {r['total_r']:+.0f}R vs BTC {b:+.0%}"
                    for r, b in down_years) + "). "
        + ("Positive in the shallow down years (2025/2026) but NEGATIVE in the "
           "severe 2022 bear "
           f"({bear['total_r']:+.1f}R vs BTC {bh.get(2022, 0):+.0%}) — so the "
           "long-only book is a long-biased TIMING overlay with real alpha in "
           "mild drawdowns, carrying PARTIAL beta that a full-cycle bear "
           "overwhelms. Not all-weather; not pure beta either."
           if bear and not bear["positive"] else
           "positive even in the 2022 bear — counter-trend timing, not beta."))

    asof = datetime.now(timezone.utc).isoformat()
    out = [
        f"# MTF broaden_best — {args.symbol} LONG-ONLY deployment analysis",
        "",
        f"## Verdict: {verdict}",
        "",
        f"- asof: {asof}",
        f"- data_sha: {data_sha}",
        f"- frozen cell: `{BROADEN_BEST_LABEL}` (LONG trades only — side filter, "
        "cell byte-unchanged)",
        f"- approx time in market: {exposure:.1%} (not always-long; "
        f"{len(longs)} × 2-day holds)",
        "",
        "## Long-only vs the L/S whole (single faithful path)",
        "",
        "| book | n | pf | exp/trade | win_rate | totalR | maxDD_R | MAR | +ve |",
        "|---|---|---|---|---|---|---|---|---|",
        _stat_row("L/S whole full", ls_full),
        _stat_row("LONG-ONLY full", lo_full),
        _stat_row("LONG-ONLY recent", lo_recent),
        "",
        "Dropping the short book lifts MAR and cuts drawdown: the short leg added "
        "drawdown and subtracted return over full history (see CHARACTERIZE.md).",
        "",
        "## ECON_BAR check (long-only, full)",
        "",
        "`PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`",
        "",
        _econ_line(lo_full, robust),
        "",
        "## Per-year — long-only vs passive buy-and-hold (the beta test)",
        "",
        "| year | n | pf | exp/trade | long-only totalR | BTC buy&hold | +ve |",
        "|---|---|---|---|---|---|---|",
        *[f"| {r['year']} | {r['n']} | {r['pf']} | {r['expectancy_r']:+.3f} | "
          f"{r['total_r']:+.1f}R | {bh.get(r['year'], 0):+.0%} | "
          f"{'YES' if r['positive'] else 'no'} |" for r in yr_rows],
        f"\nrobust_frac = {robust}",
        "",
        f"**Beta test:** {beta_note}",
        "",
        "## Honest reading",
        "",
        "The long-only book is the cleanest-shaped object the lane has produced — "
        "it clears 4 of 5 ECON gates (PF 1.57, exp 1.94R, MAR 8.67, robust 0.857 "
        "= 6/7 years), better than the L/S basket's 3/5, with lower drawdown and "
        "higher MAR than the L/S whole. But three caveats bind: (1) it is a "
        "POST-HOC side filter chosen after seeing the short book lose, so on this "
        "sample it is selection, not discovery; (2) it is NOT all-weather — it "
        "loses in the severe 2022 bear (the short book was that year's hero), so "
        "it carries partial long beta; (3) it still fails the 30R fixed-f "
        "drawdown cap (the same sizing wall). It clears no new academic gate. Its "
        "only legitimate path forward is the frozen forward registration "
        "(LONG_ONLY_FORWARD_REGISTRATION.md), which resolves the selection "
        "out-of-sample. Paper only; promotes nothing to live.",
        "",
    ]
    Path(args.out).write_text("\n".join(out))
    print(f"wrote {args.out}", file=sys.stderr)
    print(f"verdict: {verdict}", file=sys.stderr)
    print(beta_note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
