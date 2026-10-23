#!/usr/bin/env python
"""carry_measure frozen accounting run. RUN ONCE.

Measurement lane: descriptive accounting, no forecasting, no verdict.
Pinned inputs, frozen window and conventions: experiments/carry_measure/
SPEC.md. Refuses to run if RESULTS.md already exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from moonface.research.carry_measure import (SEED, WINDOW_END_MS,
                                             WINDOW_START_MS,
                                             assemble_results, load_bars_1h,
                                             load_funding, render_results_md)

PINNED = {"funding": REPO / "cache/matrix/funding_BTC_USDT_USDT.csv",
          "perp": REPO / ".backtest_cache/BTC_USDT:USDT_1h.csv",
          "spot": REPO / ".backtest_cache/BTC_USDT_1h.csv"}
OUTDIR = REPO / "experiments/carry_measure"

# Binance's own BTC/USDT spot 1h history (fetched by
# carry_measure_fetch_spot.py) is missing 31 hours across 14 gaps in the
# pinned window -- a real exchange-side gap, confirmed independently via
# ccxt against both the repo's fetch_history wrapper and a raw ccxt call.
# Per SPEC Q5-only usage and the human-approved stop-and-ask resolution
# (2026-07-16), each missing hour was spliced in from the corresponding
# Coinbase BTC/USD candle (ccxt "coinbaseexchange"), never interpolated.
# This affects Q5 (descriptive basis) only; funding accounting (Q1-Q4,
# Q6-Q7) runs entirely on the gap-free perp series and never touches spot.
SPOT_GAP_SUBSTITUTIONS_UTC = (
    "2020-02-19 12:00", "2020-02-19 13:00", "2020-02-19 14:00",
    "2020-02-19 15:00", "2020-02-19 16:00", "2020-03-04 10:00",
    "2020-04-25 02:00", "2020-04-25 03:00", "2020-06-28 02:00",
    "2020-06-28 03:00", "2020-06-28 04:00", "2020-11-30 06:00",
    "2020-12-21 14:00", "2020-12-21 15:00", "2020-12-21 16:00",
    "2020-12-21 17:00", "2020-12-25 02:00", "2021-02-11 04:00",
    "2021-03-06 02:00", "2021-04-20 02:00", "2021-04-20 03:00",
    "2021-04-25 05:00", "2021-04-25 06:00", "2021-04-25 07:00",
    "2021-08-13 02:00", "2021-08-13 03:00", "2021-08-13 04:00",
    "2021-08-13 05:00", "2021-09-29 07:00", "2021-09-29 08:00",
    "2023-03-24 13:00",
)


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding", default=str(PINNED["funding"]))
    parser.add_argument("--perp", default=str(PINNED["perp"]))
    parser.add_argument("--spot", default=str(PINNED["spot"]))
    parser.add_argument("--outdir", default=str(OUTDIR))
    parser.add_argument("--start-ms", type=int, default=WINDOW_START_MS)
    parser.add_argument("--end-ms", type=int, default=WINDOW_END_MS)
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    results_md = outdir / "RESULTS.md"
    if results_md.exists():
        print(f"REFUSING to run: {results_md} exists "
              "(run-once lane, SPEC §4; re-runs need a written amendment)")
        return 1

    funding = load_funding(args.funding, args.start_ms, args.end_ms)
    perp = load_bars_1h(args.perp, args.start_ms, args.end_ms)
    spot = load_bars_1h(args.spot, args.start_ms, args.end_ms)
    results = assemble_results(funding, perp, spot)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()
    notes = []
    if Path(args.spot) == PINNED["spot"]:
        notes.append(
            "Binance BTC/USDT spot 1h history is missing 31 hours across 14 "
            "gaps in this window (a real exchange-side gap, confirmed via "
            "two independent ccxt calls). Each missing hour was spliced in "
            "from the corresponding Coinbase BTC/USD candle (ccxt "
            "'coinbaseexchange'), never interpolated. Substituted hours "
            "(UTC): " + ", ".join(SPOT_GAP_SUBSTITUTIONS_UTC) + ". This "
            "affects Q5 (descriptive basis) only -- funding accounting "
            "(Q1-Q4, Q6-Q7) runs on the perp series alone.")
    meta = {"commit": commit, "seed": SEED, "notes": notes,
            "inputs_sha256": {name: {"path": getattr(args, name),
                                     "sha256": sha256_of(getattr(args, name))}
                              for name in ("funding", "perp", "spot")}}

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "results.json").write_text(
        json.dumps({"meta": meta, "results": results}, indent=2) + "\n")
    results_md.write_text(render_results_md(results, meta))
    print(f"wrote {results_md} and results.json (commit {commit[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
