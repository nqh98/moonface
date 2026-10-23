from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from moonface.research.universe_data import DailyRow
from moonface.research.xsection import build_universe

MONTHLY_TOP_N = 50
MIN_HISTORY_DAYS = 90
VOLUME_DAYS = 30


def month_key(ts_ms: int) -> tuple[int, int]:
    d = dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc)
    return d.year, d.month


@dataclass(frozen=True)
class MembershipSchedule:
    timestamps: list[int]
    members: list[set[str]]

    def at(self, idx: int) -> set[str]:
        return self.members[idx]


def monthly_membership(
    daily: dict[str, list[DailyRow]],
    timestamps: list[int],
    *,
    top_n: int = MONTHLY_TOP_N,
    min_history_days: int = MIN_HISTORY_DAYS,
    vol_days: int = VOLUME_DAYS,
) -> MembershipSchedule:
    """Monthly top-volume membership aligned to a 4h timestamp axis."""
    out: list[set[str]] = []
    current_month: tuple[int, int] | None = None
    current: set[str] = set()
    for ts in timestamps:
        mk = month_key(ts)
        if mk != current_month:
            current = set(
                build_universe(
                    daily,
                    asof=ts,
                    top_n=top_n,
                    min_history_days=min_history_days,
                    vol_days=vol_days,
                )
            )
            current_month = mk
        out.append(set(current))
    return MembershipSchedule(timestamps=list(timestamps), members=out)

