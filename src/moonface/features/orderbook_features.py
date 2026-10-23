"""Order-book depth imbalance feature: (bid-ask)/(bid+ask) at the ±1% band,
from data.orderbook's fetched snapshots. The fetch/cache logic itself moved
to data/orderbook.py at G4 (invariant 3: no module outside data/ performs a
network fetch or writes a cache) -- this module now holds only the pure
feature computation."""
from __future__ import annotations

from moonface.data.orderbook import Row


def imbalance_points(rows: list[Row]) -> list[tuple[int, float]]:
    """(ts, (bid-ask)/(bid+ask)); zero-liquidity snapshots dropped."""
    return [(ts, (b - a) / (b + a)) for ts, b, a in rows if b + a > 0.0]
