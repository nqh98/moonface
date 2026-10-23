from __future__ import annotations

from collections.abc import Callable

from moonface.research.breadth.signals import DAY_MS
from moonface.research.universe_data import DailyRow

_DAY_MS = 86_400_000


def build_universe_slice(
    daily: dict[str, list[DailyRow]],
    asof: int,
    rank_lo: int,
    rank_hi: int,
    min_history_days: int,
    vol_days: int,
) -> list[str]:
    """Symbols at volume-descending ranks [rank_lo:rank_hi] as of `asof`.

    Ranking is identical to xsection.build_universe (mean quote volume over
    the trailing vol_days window, listing-age floor of min_history_days); only
    the slice differs. (0, N) reproduces build_universe top_n=N exactly."""
    floor_ts = asof - min_history_days * _DAY_MS
    window_start = asof - vol_days * _DAY_MS
    ranked: list[tuple[float, str]] = []
    for sym, rows in daily.items():
        if not rows or rows[0].ts_ms > floor_ts:
            continue
        vols = [r.quote_volume for r in rows if window_start < r.ts_ms <= asof]
        if not vols:
            continue
        ranked.append((sum(vols) / len(vols), sym))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [sym for _, sym in ranked[rank_lo:rank_hi]]


def slice_membership_fn(
    daily: dict[str, list[DailyRow]],
    rank_lo: int,
    rank_hi: int,
    min_history_days: int,
    vol_days: int,
    rebalance_days: int,
) -> Callable[[str, int], bool]:
    """Point-in-time membership for a rank slice, rebuilt only on the latest
    past rebalance boundary (no look-ahead) and cached per boundary."""
    cache: dict[int, frozenset[str]] = {}
    rebalance_ms = rebalance_days * DAY_MS

    def members_at(ts: int) -> frozenset[str]:
        boundary = ts - (ts % rebalance_ms)
        if boundary not in cache:
            cache[boundary] = frozenset(
                build_universe_slice(
                    daily, boundary, rank_lo, rank_hi, min_history_days, vol_days
                )
            )
        return cache[boundary]

    return lambda sym, ts: sym in members_at(ts)
