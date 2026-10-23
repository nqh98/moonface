"""Daily breadth signals for the BTC breadth-thrust timing lane."""
from __future__ import annotations

from collections.abc import Callable

from moonface.research.universe_data import DailyRow
from moonface.features.oi_features import nonoverlap

DAY_MS = 86_400_000
EXCLUDE = frozenset({"BTCUSDT"})


def _ALWAYS(sym: str, ts: int) -> bool:
    return True


def _sorted_rows(rows: list[DailyRow]) -> list[DailyRow]:
    return sorted(rows, key=lambda row: row.ts_ms)


def ma_above_flags(rows: list[DailyRow], period: int) -> dict[int, bool]:
    rows = _sorted_rows(rows)
    out: dict[int, bool] = {}
    if period <= 0:
        return out
    closes = [row.close for row in rows]
    for i in range(period - 1, len(rows)):
        ma = sum(closes[i - period + 1:i + 1]) / period
        out[rows[i].ts_ms] = closes[i] > ma
    return out


def positive_return_flags(rows: list[DailyRow], days: int) -> dict[int, bool]:
    rows = _sorted_rows(rows)
    out: dict[int, bool] = {}
    if days <= 0:
        return out
    for i in range(days, len(rows)):
        prev = rows[i - days].close
        out[rows[i].ts_ms] = rows[i].close > prev
    return out


def _aggregate(flag_maps: dict[str, dict[int, bool]],
               is_member: Callable[[str, int], bool]) -> list[tuple[int, float]]:
    timestamps: set[int] = set()
    for flags in flag_maps.values():
        timestamps.update(flags)
    out: list[tuple[int, float]] = []
    for ts in sorted(timestamps):
        numerator = 0
        denominator = 0
        for sym, flags in flag_maps.items():
            if ts not in flags or not is_member(sym, ts):
                continue
            denominator += 1
            if flags[ts]:
                numerator += 1
        if denominator:
            out.append((ts, numerator / denominator))
    return out


def pct_above_ma_series(
    daily: dict[str, list[DailyRow]],
    period: int,
    is_member: Callable[[str, int], bool] = _ALWAYS,
    exclude: frozenset[str] = EXCLUDE,
) -> list[tuple[int, float]]:
    flag_maps = {
        sym: ma_above_flags(rows, period)
        for sym, rows in daily.items()
        if sym not in exclude
    }
    return _aggregate(flag_maps, is_member)


def breadth_momentum_series(
    daily: dict[str, list[DailyRow]],
    days: int,
    is_member: Callable[[str, int], bool] = _ALWAYS,
    exclude: frozenset[str] = EXCLUDE,
) -> list[tuple[int, float]]:
    flag_maps = {
        sym: positive_return_flags(rows, days)
        for sym, rows in daily.items()
        if sym not in exclude
    }
    return _aggregate(flag_maps, is_member)


def level_state(
    series: list[tuple[int, float]],
    long_thr: float,
    short_thr: float,
) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for ts, frac in series:
        if frac >= long_thr:
            state = "LONG"
        elif frac <= short_thr:
            state = "SHORT"
        else:
            state = "FLAT"
        out.append((ts, state))
    return out


def thrust_state(
    series: list[tuple[int, float]],
    low_band: float,
    high_band: float,
    window: int,
) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    state = "FLAT"
    values: list[float] = []
    for ts, frac in series:
        prior = values[-window:] if window > 0 else []
        touched_low = any(value <= low_band for value in prior)
        touched_high = any(value >= high_band for value in prior)
        if frac >= high_band and touched_low:
            state = "LONG"
        elif frac <= low_band and touched_high:
            state = "SHORT"
        out.append((ts, state))
        values.append(frac)
    return out


def entries_from_state(
    btc_candles,
    state: list[tuple[int, str]],
    h: int,
    day_ms: int = DAY_MS,
) -> list[tuple[int, str]]:
    transitions: list[tuple[int, str]] = []
    prev: str | None = None
    for ts, side in state:
        if side in ("LONG", "SHORT") and side != prev:
            transitions.append((ts + day_ms, side))
        prev = side

    entries: list[tuple[int, str]] = []
    bi = 0
    n = len(btc_candles)
    for available_ts, side in transitions:
        while bi < n and btc_candles[bi].timestamp_ms < available_ts:
            bi += 1
        if bi >= n:
            break
        entries.append((bi, side))

    return nonoverlap(entries, h)
