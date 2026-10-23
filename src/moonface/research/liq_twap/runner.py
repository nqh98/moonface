"""Lane 1 Track-A runner + verdict rendering."""
from __future__ import annotations

import random
from statistics import fmean

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.liq_twap.screen import (
    ATR_PERIOD,
    BLOCK_LEN,
    H_GRID,
    K_GRID,
    M_FIXED,
    PRIMARY_H,
    WINDOW,
    block_effect_z,
    cell_stats,
    event_drifts,
    screen_verdict,
)
from moonface.research.liq_twap.signals import Generator, make_liq_cascade
from moonface.features.oi_features import nonoverlap

BTC_ASSET = {
    "exchange": "binance",
    "symbol": "BTC/USDT:USDT",
    "timeframe": "1h",
    "metrics_field": "sum_open_interest",
}
START_MS = 1_598_918_400_000


def _params(k: float, require_oi_drop: bool = True) -> dict:
    return {
        "window": WINDOW,
        "k": k,
        "m": M_FIXED,
        "atr_period": ATR_PERIOD,
        "require_oi_drop": require_oi_drop,
    }


def shuffle_null_max_z(
    candles: list[Candle],
    generator: Generator,
    atr_period: int,
    block_len: int,
    seed: int,
) -> float:
    from moonface.research.drift_screen import event_outcome

    rng = random.Random(seed)
    best = 0.0
    for k in K_GRID:
        for h in H_GRID:
            events = nonoverlap(generator(candles, _params(k)), h)
            rets: list[float] = []
            for i, _ in events:
                side = "LONG" if rng.random() < 0.5 else "SHORT"
                out = event_outcome(candles, i, side, h, atr_period)
                if out is not None:
                    rets.append(out[0])
            best = max(best, block_effect_z(rets, block_len))
    return best


def run_screen(bundle: DataBundle, seed: int = 20260709) -> dict:
    candles = bundle.candles
    if bundle.feature is None:
        raise ValueError("bundle has no OI feature (metrics_field required)")
    gen = make_liq_cascade(bundle.feature)

    cells = [cell_stats(candles, gen, _params(k), h, ATR_PERIOD, BLOCK_LEN) for k in K_GRID for h in H_GRID]

    treat = event_drifts(candles, gen, _params(1.5, True), PRIMARY_H, ATR_PERIOD)
    ctrl = event_drifts(candles, gen, _params(1.5, False), PRIMARY_H, ATR_PERIOD)
    treat_mean = fmean(treat) if treat else 0.0
    ctrl_mean = fmean(ctrl) if ctrl else 0.0

    null_max_z = shuffle_null_max_z(candles, gen, ATR_PERIOD, BLOCK_LEN, seed)
    verdict = screen_verdict(cells, treat_mean, ctrl_mean, null_max_z)
    return {
        "cells": cells,
        "treat_mean": treat_mean,
        "ctrl_mean": ctrl_mean,
        "null_max_z": null_max_z,
        "verdict": verdict,
    }


def render_verdict(result: dict) -> str:
    v = result["verdict"]
    status = "PASS -> LICENSE TRACK B" if v["passed"] else "CLOSED NEGATIVE"
    lines = [
        "# lane1_twap (Track A) — verdict",
        "",
        f"- **Status:** {status}",
        "- **Lane:** Exchange Liquidation TWAP, Track A proxy pre-screen"
        " (BTC/USDT:USDT 1h, in-sample, gross, no lockbox).",
        f"- **Reason:** {v['reason']}",
        f"- **treat_mean(R)@h={PRIMARY_H}:** {result['treat_mean']:.4f} vs **ctrl_mean:** {result['ctrl_mean']:.4f}",
        f"- **null_max_effect_z:** {result['null_max_z']:.2f} (must be < 3.0)",
        "",
        "| condition | pass |",
        "|---|---|",
    ]
    for name, ok in v["conditions"].items():
        lines.append(f"| {name} | {'PASS' if ok else 'fail'} |")
    lines += ["", "| k | h | n | mean_ret_r | effect_z |", "|---:|---:|---:|---:|---:|"]
    for c in result["cells"]:
        lines.append(f"| {c['k']} | {c['h']} | {c['n']} | {c['mean_ret_r']:.4f} | {c['effect_z']:.2f} |")
    lines += [
        "",
        "Kill rule (fired if CLOSED NEGATIVE): no grid expansion, no direction flip (continuation<->reversal is Setup 3), no proxy swap, no multi-asset, no Track B without a NEW pre-registration.",
    ]
    return "\n".join(lines) + "\n"
