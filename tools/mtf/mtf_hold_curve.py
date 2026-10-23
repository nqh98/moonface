#!/usr/bin/env python3
"""Choose the MTF hold horizon from the entry's forward-return path.

The 2-day hold was inherited (the grid only compared 1d vs 2d). This derives the
hold from statistics instead: for the frozen broaden_best gate + entry
(`4h:trend_strength|rsi_reversion`), it measures the average forward R of the
gated entry as a function of holding time -- E[R(h)] -- on a train window
(selection) and confirms the shape on the recent OOS window. The hold is the
point where the drift is EXHAUSTED (marginal E[R] per day falls to <= 0), not the
argmax of a hold grid. It then deploys a fixed hold at that horizon on the
faithful single path and puts it head-to-head with the incumbent 2-day hold.

Not a re-selection of the signal: gate + entry are unchanged; only the hold
length is set by the forward path. Free Binance OHLCV; paper research, promotes
nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.kernel.econ import ECON_BAR  # noqa: E402
from moonface.research.mtf.attribute import period_stats, trade_stream  # noqa: E402
from moonface.research.mtf.basket import yearly_robustness  # noqa: E402
from moonface.research.mtf.grid import broaden_best_cell  # noqa: E402
from moonface.research.mtf.hold_curve import (forward_path,  # noqa: E402
                                              optimal_hold)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

START_MS = 1_577_836_800_000
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000     # 2024-06-01 OOS boundary
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
# 0.25d ... 6d in 15m bars
HORIZONS = [24, 48, 72, 96, 144, 192, 288, 384, 480, 576]


def _hold_cell(hold_bars: int):
    """broaden_best with only the hold length changed (gate + entry identical)."""
    bb = broaden_best_cell()
    return replace(bb, label=f"4h:trend_strength|rsi_reversion|horizon_hold@{hold_bars}b",
                   exit_name="horizon_hold",
                   exit_params={"n_bars": hold_bars, "atr_period": 14},
                   h=hold_bars)


def _curve_table(rows: list[dict]) -> list[str]:
    out = ["| hold (days) | n | E[R] | z (t) | marginal R/day |",
           "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['days']} | {r['n']} | {r['mean_r']:+.3f} | "
                   f"{r['z']:+.2f} | {r['marg_per_day']:+.3f} |")
    return out


def _dep_row(name: str, st: dict) -> str:
    return (f"| {name} | {st['n']} | {st['pf']} | {st['expectancy_r']:+.3f} | "
            f"{st['total_r']:+.1f} | {st['max_dd_r']} | {st['mar']} |")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--out", default="experiments/mtf/HOLD_CURVE.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    bb = broaden_best_cell()
    hasher = hashlib.sha256()
    sections, hold_pick = [], {}
    for sym in args.symbols:
        candles = fetch_perp_candles(sym, "15m", START_MS, END_MS, args.cache_dir)
        print(f"{sym}: {len(candles)} 15m bars", file=sys.stderr)
        hasher.update(f"{sym}:{len(candles)}".encode())
        if len(candles) < 5000:
            continue
        train = forward_path(candles, bb, HORIZONS, end_ms=RECENT_MS)
        recent = forward_path(candles, bb, HORIZONS, start_ms=RECENT_MS)
        pick = optimal_hold(train)
        hold_pick[sym] = pick
        sections += [
            f"## {sym}", "",
            "### Forward-return path — TRAIN (entries < 2024-06, selection)", "",
            *_curve_table(train), "",
            "### Forward-return path — RECENT OOS (entries >= 2024-06, confirm)", "",
            *_curve_table(recent), "",
            f"**Risk-adjusted-optimal hold (train): {pick['hold_days']} d** "
            f"(max z = per-trade Sharpe peak); E[R]={pick['mean_r']:+.3f}, "
            f"z={pick['z']:+.2f}, {'significant' if pick['significant'] else 'NOT significant'}. "
            f"Raw-E[R] peak at {pick['raw_peak_days']} d "
            f"({pick['raw_peak_mean_r']:+.3f}R, noisy tail).",
            "",
        ]
        # deployment: incumbent 2d vs the statistically-derived hold, single path
        for tag, hb in (("incumbent 2d", 192), (f"derived {pick['hold_days']}d",
                                                pick["hold_bars"])):
            st = period_stats(trade_stream(candles, _hold_cell(hb)))
            rc = period_stats(trade_stream(candles, _hold_cell(hb)),
                              start_ms=RECENT_MS)
            _, robust = yearly_robustness(trade_stream(candles, _hold_cell(hb)))
            sections += [
                f"deployment — {tag} (single path):", "",
                "| window | n | pf | exp/trade | totalR | maxDD_R | MAR |",
                "|---|---|---|---|---|---|---|",
                _dep_row("full", st), _dep_row("recent", rc),
                f"\nrobust_frac={robust} | ECON MAR floor {ECON_BAR.mar_floor}, "
                f"DD cap {ECON_BAR.max_dd_r}R", "",
            ]

    asof = datetime.now(timezone.utc).isoformat()
    head = [
        "# MTF hold horizon — derived from the entry's forward-return path", "",
        f"- asof: {asof}", f"- data_sha: {hasher.hexdigest()[:16]}",
        "- gate+entry fixed to broaden_best; only the HOLD length is set by the "
        "forward path E[R(h)]",
        "- hold rule: smallest horizon where marginal E[R] per day <= 0 (drift "
        "exhausted), on the TRAIN window, confirmed against RECENT OOS",
        "- E[R(h)] traced over ONE fixed non-overlapping trade set (constant n); "
        "z = mean / (std/sqrt n)", "",
        "## Chosen holds", "",
        "| symbol | exhaustion hold (train) | E[R] | z | significant |",
        "|---|---|---|---|---|",
        *[f"| {s} | {p['hold_days']} d | {p['mean_r']:+.3f} | {p['z']:+.2f} | "
          f"{'yes' if p['significant'] else 'no'} |" for s, p in hold_pick.items()],
        "",
    ]
    report = "\n".join(head + sections) + "\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"\nwrote {out}", file=sys.stderr)
    for s, p in hold_pick.items():
        print(f"  {s}: exhaustion hold = {p['hold_days']}d "
              f"(E[R]={p['mean_r']:+.3f}, z={p['z']:+.2f}, "
              f"raw-peak at {p['raw_peak_days']}d)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
