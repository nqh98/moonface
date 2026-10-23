"""Hermetic synthetic candle builders for the v3 engine tests."""
from __future__ import annotations

import math

from moonface.core.models import Candle

H = 3_600_000


def c(i: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(i * H, o, h, l, cl, 10.0)


def uptrend(
    n: int,
    step: float = 1.0,
    start: float = 100.0,
    wick: float = 0.2,
) -> list[Candle]:
    out: list[Candle] = []
    p = start
    for i in range(n):
        o = p
        cl = p + step
        out.append(c(i, o, max(o, cl) + wick, min(o, cl) - wick, cl))
        p = cl
    return out


def downtrend(
    n: int,
    step: float = 1.0,
    start: float = 500.0,
    wick: float = 0.2,
) -> list[Candle]:
    out: list[Candle] = []
    p = start
    for i in range(n):
        o = p
        cl = p - step
        out.append(c(i, o, max(o, cl) + wick, min(o, cl) - wick, cl))
        p = cl
    return out


def flat_range(
    n: int,
    mid: float = 100.0,
    amp: float = 2.0,
    period: int = 8,
    wick: float = 0.3,
) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        cl = mid + amp * math.sin(2 * math.pi * i / period)
        o = mid + amp * math.sin(2 * math.pi * (i - 1) / period)
        out.append(c(i, o, max(o, cl) + wick, min(o, cl) - wick, cl))
    return out
