"""Leak-proof multi-timeframe alignment.

For each base bar, find the index of the latest other-timeframe bar that is
fully closed by the time the base bar closes. Returns None where no such bar
exists. Used for 1h/1d/1w state aligned onto the 4h decision grid."""
from __future__ import annotations

from bisect import bisect_right

from moonface.core.models import Candle


def align_htf_index(base: list[Candle], htf: list[Candle], base_dur_ms: int,
                    htf_dur_ms: int) -> list[int | None]:
    """latest htf index j with htf[j].timestamp_ms + htf_dur_ms <=
    base[i].timestamp_ms + base_dur_ms, else None."""
    close_times = [c.timestamp_ms + htf_dur_ms for c in htf]
    out: list[int | None] = []
    for c in base:
        deadline = c.timestamp_ms + base_dur_ms
        j = bisect_right(close_times, deadline) - 1
        out.append(j if j >= 0 else None)
    return out
