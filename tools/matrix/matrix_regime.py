#!/usr/bin/env python3
"""Read-only regime-discovery diagnostic over the frozen BTC span (Step B).

Runs the causal walk-forward firewall and writes per-window state occupancy,
GMM train log-likelihood, and the entropy distribution. NOT an edge evaluation:
no gates, no verdict, no promotion.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.data.series import align_funding
from moonface.research.matrix.causal.pipeline import run_pipeline
from moonface.research.matrix.evaluate import (
    SEALED_START_TS_MS, SPAN_END_TS_MS, SPAN_START_TS_MS)
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles

GAP_BARS = 24
K_STATES = 3


def build_regime_report(candles, funding, *, train_bars, test_bars, step_bars,
                        gap_bars, k, seed) -> dict:
    infs, reports = run_pipeline(candles, funding, train_bars=train_bars,
                                 test_bars=test_bars, step_bars=step_bars,
                                 gap_bars=gap_bars, k=k, seed=seed)
    entropies = [r.entropy for r in infs]
    return {
        "label": "matrix step-B causal regime discovery — read-only diagnostic",
        "k_states": k,
        "state_labels": [f"State_{c}" for c in range(k)],
        "n_candles": len(candles),
        "n_windows": len(reports),
        "n_inferences": len(infs),
        "params": {"train_bars": train_bars, "test_bars": test_bars,
                   "step_bars": step_bars, "gap_bars": gap_bars, "seed": seed},
        "entropy": {
            "mean": statistics.fmean(entropies) if entropies else 0.0,
            "max": max(entropies) if entropies else 0.0},
        "windows": [{"window_index": r.window_index,
                     "train_loglik": r.train_loglik,
                     "n_test": r.n_test,
                     "occupancy": list(r.occupancy)} for r in reports],
    }


def _load(symbol, interval, start_ms, end_ms, cache_dir):
    candles = fetch_perp_candles(symbol, interval, start_ms, end_ms, cache_dir)
    points = fetch_funding_rates(symbol, start_ms, end_ms, cache_dir)
    funding = align_funding(candles, points)
    return candles, funding


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Step B causal regime diagnostic")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--cache-dir", default="cache/matrix")
    ap.add_argument("--start-ms", type=int, default=SPAN_START_TS_MS)
    ap.add_argument("--end-ms", type=int, default=SPAN_END_TS_MS)
    ap.add_argument("--train-bars", type=int, default=1000)
    ap.add_argument("--test-bars", type=int, default=100)
    ap.add_argument("--step-bars", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    btc, f_btc = _load("BTCUSDT", args.interval, args.start_ms, args.end_ms,
                       args.cache_dir)
    rep = build_regime_report(btc, f_btc, train_bars=args.train_bars,
                              test_bars=args.test_bars, step_bars=args.step_bars,
                              gap_bars=GAP_BARS, k=K_STATES, seed=args.seed)
    rep["sealed_start_ts_ms"] = SEALED_START_TS_MS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out or f"experiments/engine/matrix_regime_{stamp}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, sort_keys=True))
    print(f"windows: {rep['n_windows']}  inferences: {rep['n_inferences']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
