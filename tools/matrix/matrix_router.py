#!/usr/bin/env python3
"""Read-only AI-regime-router floor comparison over the frozen BTC 4h span."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root: tools.* under direct run

from moonface.data.series import align_funding
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.strategies import (
    donchian_reverse,
    donchian_reverse_frozen,
)
from moonface.research.matrix.evaluate import (
    SEALED_START_TS_MS,
    SPAN_END_TS_MS,
    SPAN_START_TS_MS,
)
from moonface.research.matrix.router.modes import build_bar_modes
from moonface.research.matrix.router.strategy import router_conditioned
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from tools.matrix.matrix_baselines import _finite, _metrics_cell

GAP_BARS = 24
K_STATES = 3


def build_router_report(
    candles,
    funding,
    *,
    n,
    train_bars,
    test_bars,
    step_bars,
    gap_bars,
    k,
    seed,
    entropy_freeze,
    taker_fee,
    slippage_bps,
) -> dict:
    modes = build_bar_modes(
        candles,
        funding,
        n=n,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        gap_bars=gap_bars,
        k=k,
        seed=seed,
        entropy_freeze=entropy_freeze,
    )
    strategies: dict = {"router": {}, "baseline_1": {}, "baseline_2": {}}
    for mult, key in ((1.0, "cost_1x"), (2.0, "cost_2x")):
        cost = CostModel(taker_fee=taker_fee, slippage_bps=slippage_bps, mult=mult)
        strategies["router"][key] = _metrics_cell(
            router_conditioned(candles, modes, n=n, cost=cost)
        )
        strategies["baseline_1"][key] = _metrics_cell(
            donchian_reverse(candles, n=n, cost=cost)
        )
        strategies["baseline_2"][key] = _metrics_cell(
            donchian_reverse_frozen(candles, n=n, cost=cost)
        )
    return {
        "label": "matrix step-A regime router — read-only floor comparison",
        "n_candles": len(candles),
        "n_labeled_bars": len(modes),
        "params": {
            "n": n,
            "train_bars": train_bars,
            "test_bars": test_bars,
            "step_bars": step_bars,
            "gap_bars": gap_bars,
            "k": k,
            "seed": seed,
            "entropy_freeze": entropy_freeze,
            "taker_fee": taker_fee,
            "slippage_bps": slippage_bps,
        },
        "strategies": strategies,
    }


def _load(symbol, interval, start_ms, end_ms, cache_dir):
    candles = fetch_perp_candles(symbol, interval, start_ms, end_ms, cache_dir)
    points = fetch_funding_rates(symbol, start_ms, end_ms, cache_dir)
    funding = align_funding(candles, points)
    return candles, funding


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Step A regime-router floor comparison")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--cache-dir", default="cache/matrix")
    ap.add_argument("--start-ms", type=int, default=SPAN_START_TS_MS)
    ap.add_argument("--end-ms", type=int, default=SPAN_END_TS_MS)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--train-bars", type=int, default=1000)
    ap.add_argument("--test-bars", type=int, default=100)
    ap.add_argument("--step-bars", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--entropy-freeze", type=float, default=0.90)
    ap.add_argument("--taker-fee", type=float, default=0.0004)
    ap.add_argument("--slippage-bps", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    candles, funding = _load(
        "BTCUSDT",
        args.interval,
        args.start_ms,
        args.end_ms,
        args.cache_dir,
    )
    rep = build_router_report(
        candles,
        funding,
        n=args.n,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        step_bars=args.step_bars,
        gap_bars=GAP_BARS,
        k=K_STATES,
        seed=args.seed,
        entropy_freeze=args.entropy_freeze,
        taker_fee=args.taker_fee,
        slippage_bps=args.slippage_bps,
    )
    rep["sealed_start_ts_ms"] = SEALED_START_TS_MS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out or f"experiments/engine/matrix_router_{stamp}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_finite(rep), indent=2, sort_keys=True))
    router = rep["strategies"]["router"]["cost_1x"]["full"]
    baseline_1 = rep["strategies"]["baseline_1"]["cost_1x"]["full"]
    print(
        f"router MAR={router['mar']} vs B1 MAR={baseline_1['mar']} "
        f"(labeled {rep['n_labeled_bars']}) -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
