from __future__ import annotations

import hashlib
import math

from moonface.core.models import Candle


def series_fingerprint(candles: list[Candle]) -> str:
    h = hashlib.sha256()
    for c in candles:
        h.update(f"{c.timestamp_ms},{c.close}\n".encode())
    return h.hexdigest()


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based) with tie averaging."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while (j + 1 < len(order)
               and values[order[j + 1]] == values[order[i]]):
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)
