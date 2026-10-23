"""Lane 1 Track-A drift-screen statistics and the frozen 5-condition verdict.

Per-event forward drift is measured in R via drift_screen.event_outcome, on
non-overlapping events. Effect-Z is mean / std of a moving-block-bootstrap of
the per-event drifts, reusing power_harness._resample_mean_block."""
from __future__ import annotations

import random
from collections.abc import Callable
from statistics import fmean, pstdev

from moonface.core.models import Candle
from moonface.research.drift_screen import event_outcome
from moonface.features.oi_features import nonoverlap
from moonface.kernel.power_harness import _resample_mean_block

Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]

K_GRID = (1.5, 2.0)
H_GRID = (1, 2, 3, 4)
M_FIXED = 1.5
WINDOW = 180
ATR_PERIOD = 14
BLOCK_LEN = 4
PRIMARY_H = 2
FLOOR_Z = 3.0


def event_drifts(
    candles: list[Candle],
    generator: Generator,
    params: dict,
    h: int,
    atr_period: int,
) -> list[float]:
    events = nonoverlap(generator(candles, params), h)
    rets: list[float] = []
    for i, side in events:
        out = event_outcome(candles, i, side, h, atr_period)
        if out is not None:
            rets.append(out[0])
    return rets


def block_effect_z(
    rets: list[float],
    block_len: int,
    n_resamples: int = 10_000,
    seed: int = 20260709,
) -> float:
    if len(rets) < 2:
        return 0.0
    rng = random.Random(seed)
    means = [_resample_mean_block(rng, rets, block_len) for _ in range(n_resamples)]
    sd = pstdev(means)
    if sd == 0.0:
        mean_ret = fmean(rets)
        if mean_ret > 0.0:
            return float("inf")
        if mean_ret < 0.0:
            return float("-inf")
        return 0.0
    return fmean(rets) / sd


def cell_stats(
    candles: list[Candle],
    generator: Generator,
    params: dict,
    h: int,
    atr_period: int,
    block_len: int,
) -> dict:
    rets = event_drifts(candles, generator, params, h, atr_period)
    return {
        "k": params["k"],
        "h": h,
        "n": len(rets),
        "mean_ret_r": fmean(rets) if rets else 0.0,
        "effect_z": block_effect_z(rets, block_len),
    }


def screen_verdict(
    cells: list[dict],
    treat_mean: float,
    ctrl_mean: float,
    null_max_z: float,
    floor: float = FLOOR_Z,
) -> dict:
    pooled = fmean([c["mean_ret_r"] for c in cells]) if cells else 0.0
    sign_positive = pooled > 0.0

    strong = [c for c in cells if c["effect_z"] >= floor and c["mean_ret_r"] > 0.0]
    floor_ok = len(strong) > 0

    robust = False
    for c in strong:
        same_h = [d for d in cells if d["h"] == c["h"]]
        if len(same_h) >= 2 and all(d["mean_ret_r"] > 0.0 for d in same_h):
            robust = True
            break

    treatment_gt_control = treat_mean > ctrl_mean
    null_fails = null_max_z < floor

    conditions = {
        "sign_positive": sign_positive,
        "floor": floor_ok,
        "robust": robust,
        "treatment_gt_control": treatment_gt_control,
        "null_fails": null_fails,
    }
    passed = all(conditions.values())
    failed = [name for name, ok in conditions.items() if not ok]
    reason = (
        "all 5 conditions cleared -> LICENSE Track B"
        if passed
        else "failed: " + ", ".join(failed)
    )
    return {
        "passed": passed,
        "conditions": conditions,
        "reason": reason,
        "pooled_mean_ret_r": pooled,
    }
