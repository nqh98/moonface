from __future__ import annotations

import random

from moonface.core.models import Candle

_H4_MS = 4 * 3_600_000


def make_candles(n: int, seed: int = 7, drift: float = 0.002, noise: float = 0.01,
                 start_price: float = 100.0, start_ts: int = 1_600_000_000_000,
                 timeframe_ms: int = _H4_MS) -> list[Candle]:
    """Deterministic synthetic OHLCV: geometric drift + uniform noise. Test/smoke
    fixture only — not a market model. random.Random(seed) per repo convention."""
    rng = random.Random(seed)
    out: list[Candle] = []
    price = start_price
    ts = start_ts
    for _ in range(n):
        ret = drift + rng.uniform(-noise, noise)
        close = price * (1.0 + ret)
        high = max(price, close) * (1.0 + rng.uniform(0.0, noise / 2))
        low = min(price, close) * (1.0 - rng.uniform(0.0, noise / 2))
        out.append(Candle(ts, round(price, 6), round(high, 6), round(low, 6),
                          round(close, 6), 1000.0))
        price = close
        ts += timeframe_ms
    return out
