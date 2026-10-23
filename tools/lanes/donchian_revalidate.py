#!/usr/bin/env python3
"""Pre-registered BTC 4h Donchian revalidation: run all six analyses + verdict.

Spec: docs/research-log/specs/2026-06-20-btc-4h-donchian-revalidation-design.md.
Run: .venv/bin/python tools/donchian_revalidate.py --start-ms ... --end-ms ..."""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.donchian_reval import (
    cost_stress, exit_ablation, gross_h12_probe, local_param_plateau,
    nonoverlap_walk_forward, regime_breakdown, render_result, revalidation_verdict,
    trade_distribution)
from moonface.research.trend_sim import simulate_donchian
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from tools.engine.swing_donchian import _BASE

_YEAR_BARS = {"4h": 2190}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC 4h Donchian revalidation")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="4h", choices=["4h"])
    ap.add_argument("--cache-dir", default="cache/swing")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--out", default="experiments/deployable/DONCHIAN_REVALIDATION_RESULT.md")
    args = ap.parse_args(argv)

    candles = fetch_perp_candles(args.symbol, args.interval, args.start_ms,
                                 args.end_ms, args.cache_dir)
    funding = fetch_funding_rates(args.symbol, args.start_ms, args.end_ms, args.cache_dir)
    step = _YEAR_BARS[args.interval]

    DEPLOYED = replace(_BASE, entry_n=40, trail_n=20)

    gross = gross_h12_probe(candles, n=40)
    ablation = exit_ablation(candles, funding, DEPLOYED)
    plateau = local_param_plateau(candles, funding, DEPLOYED)
    cost = cost_stress(candles, funding, DEPLOYED)
    deployed_trades = simulate_donchian(candles, DEPLOYED, funding)
    dist = trade_distribution(deployed_trades)
    regime = regime_breakdown(candles, deployed_trades)
    wf = nonoverlap_walk_forward(candles, funding, step)
    verdict = revalidation_verdict(wf, ablation, plateau, cost, dist, regime)

    sha = hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]
    asof = datetime.now(timezone.utc).isoformat()
    md = render_result(args.symbol, args.interval, len(candles), sha, asof,
                       wf, gross, ablation, plateau, cost, dist, regime, verdict)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"verdict: {verdict.tier} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
