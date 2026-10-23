from __future__ import annotations

import math

from moonface.core.models import Candle

from moonface.research.sse.clusters import UNLABELED


def entry_episodes(
    labels: list[int],
    candles: list[Candle],
    *,
    horizon: int = 24,
) -> list[dict]:
    """One observation per transition into a labeled cluster."""
    if len(labels) != len(candles):
        raise ValueError("labels/candles length mismatch")
    out: list[dict] = []
    for i, label in enumerate(labels):
        if label == UNLABELED or i == 0 or labels[i - 1] == label or i + horizon >= len(candles):
            continue
        entry = candles[i].close
        exit_ = candles[i + horizon].close
        if entry <= 0 or exit_ <= 0:
            continue
        out.append(
            {
                "ts_ms": candles[i].timestamp_ms,
                "cluster": label,
                "fwd_r": math.log(exit_ / entry),
            }
        )
    return out


def assign_eras(timestamps: list[int], era_bounds: list[tuple[int, int]]) -> list[int | None]:
    eras: list[int | None] = []
    for ts in timestamps:
        era = None
        for idx, (start, end) in enumerate(era_bounds, start=1):
            if start <= ts < end:
                era = idx
                break
        eras.append(era)
    return eras

