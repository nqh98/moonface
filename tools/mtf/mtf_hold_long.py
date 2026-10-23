#!/usr/bin/env python3
"""Long-horizon forward-return scan for the MTF entry — BTC, out to 100 days.

The 6-day curve (mtf_hold_curve) shows the counter-trend edge exhausting by ~3
days. This asks the opposite question: does a SECOND, trend-following payoff
re-emerge if the same gated entry is held for weeks to months -- and if so, is it
a real edge or just BTC's long-run directional beta? For the frozen broaden_best
gate + entry it scans E[R(h)] at holds from 1 to 100 days, each horizon on its own
maximal non-overlapping (independent) sample, split full / train / recent, with
the long/short mix shown so a long-side beta drift can't masquerade as edge.

Diagnostic only (long holds leave too few non-overlapping trades to deploy or
size). Free Binance OHLCV; paper research, promotes nothing to live."""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.mtf.grid import broaden_best_cell  # noqa: E402
from moonface.research.mtf.hold_curve import long_horizon_scan  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

START_MS = 1_577_836_800_000
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000     # 2024-06-01 OOS boundary
# 1d ... 100d in 15m bars (1 day = 96 bars)
HORIZON_DAYS = [1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 80, 100]


def _table(title: str, rows: list[dict]) -> list[str]:
    out = [f"### {title}", "",
           "| hold (days) | n | L/S | E[R] | z (t) |",
           "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['days']:g} | {r['n']} | {r['longs']}/{r['shorts']} | "
                   f"{r['mean_r']:+.3f} | {r['z']:+.2f} |")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT"])
    ap.add_argument("--dense", action="store_true",
                    help="scan EVERY day 1..max-days instead of the sparse grid")
    ap.add_argument("--max-days", type=int, default=100)
    ap.add_argument("--out", default="experiments/mtf/HOLD_LONG.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    bb = broaden_best_cell()
    days = (list(range(1, args.max_days + 1)) if args.dense
            else [d for d in HORIZON_DAYS if d <= args.max_days])
    horizons = [d * 96 for d in days]
    hasher, sections = hashlib.sha256(), []
    for sym in args.symbols:
        candles = fetch_perp_candles(sym, "15m", START_MS, END_MS, args.cache_dir)
        print(f"{sym}: {len(candles)} 15m bars", file=sys.stderr)
        hasher.update(f"{sym}:{len(candles)}".encode())
        if len(candles) < 5000:
            continue
        full = long_horizon_scan(candles, bb, horizons)
        train = long_horizon_scan(candles, bb, horizons, end_ms=RECENT_MS)
        recent = long_horizon_scan(candles, bb, horizons, start_ms=RECENT_MS)
        sig = [r for r in full if abs(r["z"]) >= 2.0]
        sections += [
            f"## {sym}", "",
            *_table("FULL history", full), "",
            *_table("TRAIN (< 2024-06)", train), "",
            *_table("RECENT OOS (>= 2024-06)", recent), "",
            "**Significant (|z|>=2) long holds (full): "
            + (", ".join(f"{r['days']:g}d (z {r['z']:+.2f}, L/S {r['longs']}/"
                         f"{r['shorts']})" for r in sig) if sig else "none")
            + "**", "",
        ]
        print(f"  {sym}: significant long holds = "
              f"{[r['days'] for r in sig] or 'none'}", file=sys.stderr)

    asof = datetime.now(timezone.utc).isoformat()
    head = [
        "# MTF long-horizon forward-return scan (1–100 days)", "",
        f"- asof: {asof}", f"- data_sha: {hasher.hexdigest()[:16]}",
        "- gate+entry fixed to broaden_best (`4h:trend_strength|rsi_reversion`); "
        "only the forward horizon varies",
        "- each horizon on its OWN non-overlapping sample (max independent n); "
        "z = mean/(std/sqrt n)",
        "- diagnostic only: long holds leave too few independent trades to deploy",
        "- read L/S: at long holds an all-long-and-BTC-rose drift is beta, not "
        "the counter-trend edge", "",
    ]
    report = "\n".join(head + sections) + "\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
