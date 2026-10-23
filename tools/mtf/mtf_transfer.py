#!/usr/bin/env python3
"""Cross-asset transfer test for the frozen MTF headline signal.

Runs the SAME frozen cell (1d trend regime + 15m RSI counter-trend entry + 2-day
hold behind a 3xATR wide stop) on ETH and SOL, with BTC as the in-sample control.
A genuine transfer = same SIGN and a positive recent (out-of-sample) period on
assets the signal was not chosen on.

CAVEAT: crypto majors are highly correlated, so ETH/SOL are not fully independent
of BTC (shared beta). This tests whether the *mechanism* generalises, not whether
the edge is market-neutral. Free Binance OHLCV only; paper research, promotes
nothing to live."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.mtf.attribute import period_stats, trade_stream  # noqa: E402
from moonface.research.mtf.grid import (HEADLINE_LABEL, BASE_TF,  # noqa: E402
                                        headline_cell)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

START_MS = 1_577_836_800_000   # 2020-01-01 UTC
END_MS = 1_782_000_000_000
RECENT_MS = 1_717_200_000_000  # 2024-06-01: the out-of-sample recent window
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _row(sym: str, tag: str, st: dict) -> str:
    return (f"| {sym} | {tag} | {st['n']} | {st['longs']}/{st['shorts']} | "
            f"{st['pf']} | {st['expectancy_r']:+.3f} | {st['total_r']:+.1f} | "
            f"{st['max_dd_r']} | {st['mar']} | "
            f"{'YES' if st['positive'] else 'no'} |")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cache-dir", default="cache/mtf")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--out", default="experiments/mtf/TRANSFER.md")
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 0

    cell = headline_cell()
    rows, summary = [], []
    for sym in args.symbols:
        candles = fetch_perp_candles(sym, BASE_TF, START_MS, END_MS, args.cache_dir)
        print(f"{sym}: {len(candles)} {BASE_TF} bars", file=sys.stderr)
        if len(candles) < 5000:
            rows.append(f"| {sym} | — | insufficient data ({len(candles)} bars) |")
            continue
        trades = trade_stream(candles, cell)
        full = period_stats(trades)
        recent = period_stats(trades, start_ms=RECENT_MS)
        rows.append(_row(sym, "full", full))
        rows.append(_row(sym, "recent", recent))
        summary.append((sym, full, recent))

    asof = datetime.now(timezone.utc).isoformat()
    # transfer verdict: every non-control asset positive in BOTH full and recent
    non_control = [s for s in summary if s[0] != "BTCUSDT"]
    transferred = bool(non_control) and all(
        f["positive"] and r["positive"] for _, f, r in non_control)
    verdict = ("TRANSFERS (sign holds + recent-positive on every non-BTC asset)"
               if transferred else
               "DOES NOT cleanly transfer (see per-asset rows)")
    report = (
        "# MTF Headline Signal — Cross-Asset Transfer Test\n\n"
        f"## Verdict: {verdict}\n\n"
        f"- asof: {asof}\n- frozen cell: `{HEADLINE_LABEL}`\n"
        f"- recent window: entries >= {RECENT_MS} (2024-06, out-of-sample)\n"
        "- BTC = in-sample control; ETH/SOL = transfer targets\n\n"
        "| asset | period | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(rows) +
        "\n\n## Caveat\n\nCrypto majors share beta, so ETH/SOL are correlated "
        "confirmations, not independent ones. Each asset is gated by its OWN 1d "
        "trend, so this tests mechanism generalisation; a market-neutral claim "
        "would need a BTC hedge (see the program's breadth-neutral finding).\n")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
