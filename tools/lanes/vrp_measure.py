#!/usr/bin/env python
"""vrp_measure frozen measurement run. RUN ONCE.

Measurement lane: descriptive accounting, no forecasting, no verdict. Pinned
inputs, frozen window and conventions: experiments/vrp_measure/SPEC.md.
Refuses to run if RESULTS.md already exists.
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

from moonface.research.vrp_measure import (HOUR_MS, N_NULL_SEEDS,  # noqa: E402
                                           RV_HORIZON_HOURS, WINDOW_END_MS,
                                           WINDOW_START_MS, assemble_results,
                                           build_return_series, load_dvol,
                                           load_spot_closes, render_results_md)

PINNED = {"dvol": REPO / "cache/exogenous/dvol_BTC_43200_full.csv",
          "spot": REPO / ".backtest_cache/BTC_USDT_1h.csv"}
OUTDIR = REPO / "experiments/vrp_measure"

SPLICE_NOTE = (
    "Realized variance is measured on Binance BTC/USDT spot 1h closes. Twelve "
    "bars inside this window are not Binance data: they are Coinbase BTC/USD "
    "candles spliced in by carry_measure under the human-approved 2026-07-16 "
    "resolution of a real exchange-side gap (2021-04-20, 2021-04-25, "
    "2021-08-13, 2021-09-29, 2023-03-24). Each splice boundary creates an "
    "artificial cross-exchange price step, so log returns straddling a boundary "
    "are excluded from the sum of squares and each window divides by its actual "
    "usable return count. Returns interior to a spliced run are kept. Nothing "
    "is interpolated (SPEC section 3.3).")


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dvol", default=str(PINNED["dvol"]))
    parser.add_argument("--spot", default=str(PINNED["spot"]))
    parser.add_argument("--outdir", default=str(OUTDIR))
    parser.add_argument("--start-ms", type=int, default=WINDOW_START_MS)
    parser.add_argument("--end-ms", type=int, default=WINDOW_END_MS)
    parser.add_argument("--null-seeds", type=int, default=N_NULL_SEEDS,
                        help="testing hook only; the frozen run uses the default")
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    results_md = outdir / "RESULTS.md"
    if results_md.exists():
        print(f"REFUSING to run: {results_md} exists "
              "(run-once lane, SPEC section 3.4; re-runs need a written amendment)")
        return 1

    dvol = load_dvol(args.dvol, args.start_ms, args.end_ms)
    last_ret_ts = args.end_ms + (RV_HORIZON_HOURS - 1) * HOUR_MS
    closes = load_spot_closes(args.spot, args.start_ms - HOUR_MS, last_ret_ts)
    series = build_return_series(closes, args.start_ms, last_ret_ts)
    results = assemble_results(dvol, series, n_null_seeds=args.null_seeds)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()
    meta = {"commit": commit, "notes": [SPLICE_NOTE],
            "inputs_sha256": {name: {"path": getattr(args, name),
                                     "sha256": sha256_of(getattr(args, name))}
                              for name in ("dvol", "spot")}}

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "results.json").write_text(
        json.dumps({"meta": meta, "results": results}, indent=2) + "\n")
    results_md.write_text(render_results_md(results, meta))
    print(f"wrote {results_md} and results.json (commit {commit[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
