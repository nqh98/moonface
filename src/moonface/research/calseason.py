from __future__ import annotations

import datetime as dt
from statistics import fmean

from moonface.core.models import Candle
from moonface.features.oi_features import stouffer

CELLS = ("funding_pre", "funding_post", "weekend", "weekday")
FUNDING_PRE_HOURS = {4, 12, 20}
FUNDING_POST_HOURS = {0, 8, 16}

MIN_ASSETS = 8
MIN_RETURNS = 30
MIN_BREADTH = 12
ABS_STOUFFER_GATE = 3.0


def cell_names(ts_ms: int) -> list[str]:
    d = dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc)
    cells: list[str] = []
    if d.hour in FUNDING_PRE_HOURS:
        cells.append("funding_pre")
    if d.hour in FUNDING_POST_HOURS:
        cells.append("funding_post")
    cells.append("weekend" if d.weekday() >= 5 else "weekday")
    return cells


def cell_returns(candles: list[Candle]) -> dict[str, list[float]]:
    out = {name: [] for name in CELLS}
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        if prev == 0.0:
            continue
        r = candles[i].close / prev - 1.0
        for name in cell_names(candles[i].timestamp_ms):
            out[name].append(r)
    return out


def _sign(x: float) -> int:
    if x > 0.0:
        return 1
    if x < 0.0:
        return -1
    return 0


def pooled_cell(stats: list[dict]) -> dict:
    evaluable = [s for s in stats if s["n"] >= MIN_RETURNS]
    if not evaluable:
        return {"m": 0, "pooled_mean": 0.0, "effect_sign": 0,
                "same_sign": 0, "stouffer_z": 0.0,
                "abs_stouffer_z": 0.0}
    mean = fmean([s["mean"] for s in evaluable])
    effect_sign = _sign(mean)
    z = stouffer([s["t"] for s in evaluable])
    same_sign = sum(1 for s in evaluable if _sign(s["mean"]) == effect_sign)
    return {"m": len(evaluable), "pooled_mean": mean,
            "effect_sign": effect_sign, "same_sign": same_sign,
            "stouffer_z": z, "abs_stouffer_z": abs(z)}


def _stable(summary: dict, halves: dict) -> bool:
    sign = summary["effect_sign"]
    if sign == 0:
        return False
    return (_sign(halves["first"]["pooled_mean"]) == sign
            and _sign(halves["second"]["pooled_mean"]) == sign)


def calseason_verdict(cell_stats: dict[str, list[dict]],
                      halves: dict[str, dict[str, dict]]) -> dict:
    cells = {}
    winners: list[str] = []
    for name in CELLS:
        summary = pooled_cell(cell_stats[name])
        summary["stable_halves"] = _stable(summary, halves[name])
        summary["clears_gate"] = (
            summary["m"] >= MIN_ASSETS
            and summary["abs_stouffer_z"] > ABS_STOUFFER_GATE
            and summary["same_sign"] >= MIN_BREADTH
            and summary["stable_halves"]
        )
        cells[name] = summary
        if summary["clears_gate"]:
            winners.append(name)
    winner = max(winners, key=lambda n: cells[n]["abs_stouffer_z"]) if winners else None
    return {
        "status": "closed_positive" if winner else "closed_negative",
        "winner": winner,
        "reason": (
            f"{winner} clears fixed calendar gate"
            if winner else "no fixed calendar cell clears the frozen gate"
        ),
        "cells": cells,
    }
