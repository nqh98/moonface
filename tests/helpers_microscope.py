"""Synthetic pools for microscope tests — hermetic, no disk or network."""
from __future__ import annotations

import random

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle

STEP_MS = 14_400_000            # 4h
TS0 = 1_600_000_000_000


def make_candles(n: int, seed: int = 1, drift: float = 0.0,
                 start: float = 100.0) -> list[Candle]:
    rng = random.Random(seed)
    price = start
    out: list[Candle] = []
    for i in range(n):
        nxt = price * (1.0 + drift + rng.gauss(0.0, 0.01))
        hi = max(price, nxt) * 1.002
        lo = min(price, nxt) * 0.998
        out.append(Candle(timestamp_ms=TS0 + i * STEP_MS, open=price,
                          high=hi, low=lo, close=nxt,
                          volume=1000.0 + rng.random() * 100.0))
        price = nxt
    return out


def make_bundle(n: int, seed: int = 1, drift: float = 0.0) -> DataBundle:
    candles = make_candles(n, seed=seed, drift=drift)
    rng = random.Random(seed + 999)
    funding = [rng.gauss(0.0001, 0.0002) for _ in range(n)]
    oi: list[float | None] = []
    level = 1_000_000.0
    for _ in range(n):
        level *= 1.0 + rng.gauss(0.0, 0.005)
        oi.append(level)
    return DataBundle(candles=candles, funding=funding, feature=oi)


def make_pool(n: int = 400, n_assets: int = 10,
              seed: int = 1) -> dict[str, DataBundle]:
    pool = {f"A{a:02d}USDT": make_bundle(n, seed=seed + a)
            for a in range(n_assets)}
    pool["BTCUSDT"] = make_bundle(n, seed=seed + 100)
    return pool
