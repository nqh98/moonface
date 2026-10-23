#!/usr/bin/env python3
"""Read-only ablation-baseline floor diagnostic over the frozen BTC 4h span."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.data.series import align_funding
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.metrics import baseline_metrics
from moonface.research.matrix.baselines.strategies import (
    donchian_reverse,
    donchian_reverse_frozen,
)
from moonface.research.matrix.evaluate import (
    SEALED_START_TS_MS,
    SPAN_END_TS_MS,
    SPAN_START_TS_MS,
)
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles


def _finite(obj):
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return "inf" if obj > 0 else "-inf"
    return obj


def _metrics_cell(trades):
    train = [t for t in trades if t.entry_ts_ms < SEALED_START_TS_MS]
    sealed = [t for t in trades if t.entry_ts_ms >= SEALED_START_TS_MS]
    return {
        "full": asdict(baseline_metrics(trades)),
        "segments": {
            "train": asdict(baseline_metrics(train)),
            "sealed": asdict(baseline_metrics(sealed)),
        },
    }


def build_baseline_report(
    candles,
    *,
    n,
    atr_period,
    freeze_pctl,
    freeze_lookback,
    taker_fee,
    slippage_bps,
) -> dict:
    baselines: dict[str, dict] = {"baseline_1": {}, "baseline_2": {}}
    for mult, key in ((1.0, "cost_1x"), (2.0, "cost_2x")):
        cost = CostModel(taker_fee=taker_fee, slippage_bps=slippage_bps, mult=mult)
        b1 = donchian_reverse(candles, n=n, cost=cost)
        b2 = donchian_reverse_frozen(
            candles,
            n=n,
            atr_period=atr_period,
            freeze_pctl=freeze_pctl,
            freeze_lookback=freeze_lookback,
            cost=cost,
        )
        baselines["baseline_1"][key] = _metrics_cell(b1)
        baselines["baseline_2"][key] = _metrics_cell(b2)
    return {
        "label": "matrix step-C ablation baselines - read-only floor diagnostic",
        "n_candles": len(candles),
        "params": {
            "n": n,
            "atr_period": atr_period,
            "freeze_pctl": freeze_pctl,
            "freeze_lookback": freeze_lookback,
            "taker_fee": taker_fee,
            "slippage_bps": slippage_bps,
        },
        "baselines": baselines,
    }


def _load(symbol, interval, start_ms, end_ms, cache_dir):
    candles = fetch_perp_candles(symbol, interval, start_ms, end_ms, cache_dir)
    points = fetch_funding_rates(symbol, start_ms, end_ms, cache_dir)
    # Loaded for parity with Step B data access; funding is a documented deferral here.
    align_funding(candles, points)
    return candles


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Step C ablation-baseline floor")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--cache-dir", default="cache/matrix")
    ap.add_argument("--start-ms", type=int, default=SPAN_START_TS_MS)
    ap.add_argument("--end-ms", type=int, default=SPAN_END_TS_MS)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--atr-period", type=int, default=14)
    ap.add_argument("--freeze-pctl", type=float, default=0.80)
    ap.add_argument("--freeze-lookback", type=int, default=500)
    ap.add_argument("--taker-fee", type=float, default=0.0004)
    ap.add_argument("--slippage-bps", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    candles = _load("BTCUSDT", args.interval, args.start_ms, args.end_ms, args.cache_dir)
    rep = build_baseline_report(
        candles,
        n=args.n,
        atr_period=args.atr_period,
        freeze_pctl=args.freeze_pctl,
        freeze_lookback=args.freeze_lookback,
        taker_fee=args.taker_fee,
        slippage_bps=args.slippage_bps,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out or f"experiments/engine/matrix_baselines_{stamp}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_finite(rep), indent=2, sort_keys=True))
    b1 = rep["baselines"]["baseline_1"]["cost_1x"]["full"]
    print(f"B1 trades={b1['trade_count']} MAR={b1['mar']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
