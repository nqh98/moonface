#!/usr/bin/env python3
"""One pre-registered Slice-1 matrix evaluation. Read-only; human promotion.

Spends the sealed BTC year only if Gate 1 passes. Requires the v2.2 baseline
validation/sealed max_dd_r (compute the way v3/evaluate.py derives base_val/base_sealed).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.data.series import align_funding
from moonface.research.trend_sim import TrendParams
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from moonface.research.matrix.evaluate import build_matrix_report


def _load(symbol, interval, start_ms, end_ms, cache_dir):
    candles = fetch_perp_candles(symbol, interval, start_ms, end_ms, cache_dir)
    # fetch_funding_rates yields (ts, rate) points; make_funding_fade needs a
    # per-candle-aligned list[float|None] (as-of join, no lookahead).
    points = fetch_funding_rates(symbol, start_ms, end_ms, cache_dir)
    funding = align_funding(candles, points)
    return candles, funding


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Matrix Slice-1 evaluation")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--cache-dir", default="cache/matrix")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--baseline-val-dd", type=float, required=True,
                    help="v2.2 baseline validation max_dd_r (negative)")
    ap.add_argument("--baseline-sealed-dd", type=float, required=True,
                    help="v2.2 baseline sealed max_dd_r (negative)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    cfg = TrendParams(entry_n=20, trail_n=10, atr_period=14, k_stop=2.0,
                      long_only=True, fee_rate=0.0, slippage=0.0,
                      funding_enabled=False)
    btc, f_btc = _load("BTCUSDT", args.interval, args.start_ms, args.end_ms,
                       args.cache_dir)
    eth, f_eth = _load("ETHUSDT", args.interval, args.start_ms, args.end_ms,
                       args.cache_dir)
    sol, f_sol = _load("SOLUSDT", args.interval, args.start_ms, args.end_ms,
                       args.cache_dir)

    report = build_matrix_report(btc, eth, sol, f_btc, f_eth, f_sol, cfg,
                                 args.baseline_val_dd, args.baseline_sealed_dd)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out or f"experiments/engine/matrix_slice1_{stamp}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"verdict: {report['verdict']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
