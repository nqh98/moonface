#!/usr/bin/env python3
"""Regime-flip exit — head-to-head vs the frozen fixed-hold and wide-stop exits.

Holds the 4h regime-QUALITY gate and 15m RSI counter-trend entry fixed (the
broaden_best spec) and swaps ONLY the exit, three ways:

  horizon_hold@2d   -- broaden_best: a fixed 2-day time exit, no stop (champion)
  horizon_wide_stop -- the same hold behind a 3xATR wide stop (already tested worse)
  regime_flip@2d    -- NEW structural exit: close when the same 4h trend_strength
                       gate that authorized the trade stops supporting it (flips
                       sign or decays into chop), 2-day backstop cap

Every cell is scored on the SAME faithful single-path equity curve (attribute.
trade_stream / period_stats), full history and the recent OOS window, with the
per-year robustness and the deployable ECON_BAR check, so the comparison is
apples-to-apples: does exiting on the trend-break beat the fixed time hold?

This is a parallel single follow-up cell, NOT a re-selection: it is not a member
of the frozen 72-cell broadened grid and carries no new DSR deflation. The
frozen headline / broaden_best / Slice-3 specs are untouched. Free Binance
OHLCV only; paper research, promotes nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.kernel.econ import ECON_BAR  # noqa: E402
from moonface.research.mtf.attribute import period_stats, trade_stream  # noqa: E402
from moonface.research.mtf.basket import yearly_robustness  # noqa: E402
from moonface.research.mtf.grid import (broaden_best_cell,  # noqa: E402
                                        broadened_cells, regime_flip_cell)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000  # 2024-06-01: the out-of-sample recent window
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
_WIDE_STOP_LABEL = "4h:trend_strength|rsi_reversion|horizon_wide_stop@2d"


def _wide_stop_cell():
    return next(c for c in broadened_cells() if c.label == _WIDE_STOP_LABEL)


# The three sibling exits, identical gate + entry, ordered fixed -> stop -> structural.
_EXITS = [("horizon_hold (fixed 2d, champion)", broaden_best_cell),
          ("horizon_wide_stop (3xATR)", _wide_stop_cell),
          ("regime_flip (structural, NEW)", regime_flip_cell)]


def _econ(st: dict, robust: float) -> tuple[bool, str]:
    b = ECON_BAR
    checks = [
        ("PF", st["pf"], st["pf"] >= b.profit_factor),
        ("exp", round(st["expectancy_r"], 3), st["expectancy_r"] >= b.expectancy_r),
        ("MAR", st["mar"], st["mar"] >= b.mar_floor),
        ("DD", st["max_dd_r"], abs(st["max_dd_r"]) <= b.max_dd_r),
        ("robust", robust, robust >= b.robust_frac),
    ]
    passed = all(ok for _, _, ok in checks)
    line = " | ".join(f"{n} {v} {'PASS' if ok else 'FAIL'}" for n, v, ok in checks)
    return passed, line


def _row(name: str, st: dict) -> str:
    return (f"| {name} | {st['n']} | {st['longs']}/{st['shorts']} | {st['pf']} | "
            f"{st['expectancy_r']:+.3f} | {st['total_r']:+.1f} | {st['max_dd_r']} | "
            f"{st['mar']} | {st['win_rate']} | {'YES' if st['positive'] else 'no'} |")


def _cell_section(title: str, stream) -> tuple[list[str], bool]:
    full = period_stats(stream)
    recent = period_stats(stream, start_ms=RECENT_MS)
    yr_rows, robust = yearly_robustness(stream)
    passed, econ_line = _econ(full, robust)
    lines = [
        f"### {title}", "",
        "| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |",
        "|---|---|---|---|---|---|---|---|---|---|",
        _row("full", full), _row("recent (>=2024-06)", recent), "",
        f"per-year positive: {sum(1 for r in yr_rows if r['positive'])}"
        f"/{len(yr_rows)}  (robust_frac = {robust})", "",
        "ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / "
        "robust>=0.60`", "",
        f"**{'CLEARS' if passed else 'DOES NOT CLEAR'} ECON_BAR** — {econ_line}",
        "",
    ]
    return lines, passed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--out", default="experiments/mtf/REGIME_FLIP.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    hasher = hashlib.sha256()
    sections: list[str] = []
    summary: list[tuple[str, str, dict, dict]] = []  # (sym, exit, full, recent)
    for sym in args.symbols:
        candles = fetch_perp_candles(sym, "15m", START_MS, END_MS, args.cache_dir)
        print(f"{sym}: {len(candles)} 15m bars", file=sys.stderr)
        hasher.update(f"{sym}:{len(candles)}".encode())
        if len(candles) < 5000:
            print(f"  skipped ({len(candles)} bars)", file=sys.stderr)
            continue
        sections.append(f"## {sym}\n")
        for exit_name, cell_fn in _EXITS:
            stream = trade_stream(candles, cell_fn())
            lines, _ = _cell_section(exit_name, stream)
            sections.extend(lines)
            summary.append((sym, exit_name, period_stats(stream),
                            period_stats(stream, start_ms=RECENT_MS)))

    asof = datetime.now(timezone.utc).isoformat()
    head = [
        "# MTF regime-flip exit — head-to-head vs fixed-hold / wide-stop", "",
        f"- asof: {asof}", f"- data_sha: {hasher.hexdigest()[:16]}",
        "- gate+entry fixed to broaden_best (`4h:trend_strength|rsi_reversion`); "
        "only the EXIT varies",
        "- faithful single-path (non-overlapping, per-trade R); recent window "
        ">= 2024-06-01",
        "- regime_flip is a parallel follow-up cell (not in the frozen 72-grid, "
        "no DSR deflation); promotes nothing to live", "",
        "## Head-to-head summary (recent OOS = the trust anchor)", "",
        "| symbol | exit | full pf | full MAR | full DD | recent pf | recent "
        "exp | recent n |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sym, ex, full, recent in summary:
        head.append(
            f"| {sym} | {ex} | {full['pf']} | {full['mar']} | {full['max_dd_r']} "
            f"| {recent['pf']} | {recent['expectancy_r']:+.3f} | {recent['n']} |")
    head.append("")

    report = "\n".join(head + sections) + "\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"\nwrote {out}", file=sys.stderr)
    for sym, ex, full, recent in summary:
        print(f"  {sym:8} {ex:34} full pf={full['pf']} mar={full['mar']} "
              f"dd={full['max_dd_r']} | recent pf={recent['pf']} "
              f"exp={recent['expectancy_r']:+.3f} n={recent['n']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
