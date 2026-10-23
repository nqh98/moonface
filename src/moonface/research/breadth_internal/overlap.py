from __future__ import annotations

from moonface.research.breadth.signals import DAY_MS


def overlapping_entries_from_state(btc_candles, state, h, day_ms=DAY_MS):
    """Map a daily LONG/SHORT/FLAT state to BTC entries with one entry per
    active day (no transition gate, no nonoverlap dedup). Each active day's
    entry is placed at the first bar available the next day; the hold is
    enforced downstream by the frozen exit, so ``h`` is accepted only for
    interface parity with ``entries_from_state``."""
    active = [(ts + day_ms, side) for ts, side in state if side in ("LONG", "SHORT")]
    entries: list[tuple[int, str]] = []
    bi = 0
    n = len(btc_candles)
    for available_ts, side in active:
        while bi < n and btc_candles[bi].timestamp_ms < available_ts:
            bi += 1
        if bi >= n:
            break
        entries.append((bi, side))
    return entries
