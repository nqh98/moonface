from __future__ import annotations

DAY_MS = 86_400_000


def aligned_value_at(points, decision_ts_ms: int, publish_lag_days: int) -> float | None:
    """Most recent value whose publication time <= decision time.

    Publication time = sample ts + publish_lag_days. This enforces both the
    publication lag and weekend/holiday forward-fill with zero look-ahead.
    `points` must be ascending by ts_ms (Task 2/3 guarantee this).
    """
    lag = publish_lag_days * DAY_MS
    chosen = None
    for p in points:
        if p.ts_ms + lag <= decision_ts_ms:
            chosen = p.value
        else:
            break
    return chosen


def pct_change(points, decision_ts_ms: int, lag_days: int, lookback_days: int):
    now = aligned_value_at(points, decision_ts_ms, lag_days)
    past = aligned_value_at(points, decision_ts_ms - lookback_days * DAY_MS, lag_days)
    if now is None or past is None or past == 0.0:
        return None
    return now / past - 1.0
