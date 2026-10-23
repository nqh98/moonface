from __future__ import annotations

from statistics import fmean, stdev

from moonface.core.models import Candle
from moonface.research.breadth.signals import (
    DAY_MS,
    EXCLUDE,
    _ALWAYS,
    _aggregate,
    _sorted_rows,
    pct_above_ma_series,
    level_state,
)
from moonface.research.universe_data import DailyRow


def btc_daily_closes(btc: list[Candle], day_ts: list[int]) -> dict[int, float]:
    btc = sorted(btc, key=lambda candle: candle.timestamp_ms)
    out: dict[int, float] = {}
    bi = 0
    last_close: float | None = None
    for ts in sorted(day_ts):
        while bi < len(btc) and btc[bi].timestamp_ms <= ts:
            last_close = btc[bi].close
            bi += 1
        if last_close is not None:
            out[ts] = last_close
    return out


def _direction(cur: float, prev: float) -> int:
    if cur > prev:
        return 1
    if cur < prev:
        return -1
    return 0


def _extreme_flags(rows: list[DailyRow], n: int, kind: str) -> dict[int, bool]:
    rows = _sorted_rows(rows)
    out: dict[int, bool] = {}
    if n <= 0:
        return out
    closes = [row.close for row in rows]
    for i in range(n - 1, len(rows)):
        window = closes[i - n + 1:i + 1]
        if kind == "high":
            out[rows[i].ts_ms] = closes[i] >= max(window)
        elif kind == "low":
            out[rows[i].ts_ms] = closes[i] <= min(window)
        else:
            raise ValueError(f"unknown extreme kind {kind!r}")
    return out


def net_new_highs_series(
    daily: dict[str, list[DailyRow]],
    n: int,
    is_member=_ALWAYS,
    exclude: frozenset[str] = EXCLUDE,
) -> list[tuple[int, float]]:
    high_maps = {
        sym: _extreme_flags(rows, n, "high")
        for sym, rows in daily.items()
        if sym not in exclude
    }
    low_maps = {
        sym: _extreme_flags(rows, n, "low")
        for sym, rows in daily.items()
        if sym not in exclude
    }
    highs = dict(_aggregate(high_maps, is_member))
    lows = dict(_aggregate(low_maps, is_member))
    timestamps = sorted(set(highs) & set(lows))
    return [(ts, highs.get(ts, 0.0) - lows.get(ts, 0.0)) for ts in timestamps]


def net_new_highs_state(
    daily: dict[str, list[DailyRow]],
    n: int,
    long_thr: float,
    short_thr: float,
    is_member=_ALWAYS,
) -> list[tuple[int, str]]:
    series = net_new_highs_series(daily, n, is_member=is_member)
    return level_state(series, long_thr, short_thr)


def breadth_divergence_state(
    daily: dict[str, list[DailyRow]],
    btc: list[Candle],
    n: int,
    base_period: int = 50,
    is_member=_ALWAYS,
) -> list[tuple[int, str]]:
    if n <= 0:
        return []
    breadth = dict(pct_above_ma_series(daily, base_period, is_member=is_member))
    if not breadth:
        return []

    breadth_ts = list(breadth)
    needed_ts = set(breadth_ts)
    for idx in range(n, len(breadth_ts)):
        needed_ts.add(breadth_ts[idx - n])
    btc_closes = btc_daily_closes(btc, sorted(needed_ts))

    out: list[tuple[int, str]] = []
    for idx, ts in enumerate(breadth_ts):
        if idx < n:
            out.append((ts, "FLAT"))
            continue
        prev_ts = breadth_ts[idx - n]
        if ts not in btc_closes or prev_ts not in btc_closes:
            out.append((ts, "FLAT"))
            continue
        btc_dir = _direction(btc_closes[ts], btc_closes[prev_ts])
        breadth_dir = _direction(breadth[ts], breadth[prev_ts])
        if btc_dir < 0 and breadth_dir > 0:
            side = "LONG"
        elif btc_dir > 0 and breadth_dir < 0:
            side = "SHORT"
        else:
            side = "FLAT"
        out.append((ts, side))
    return out


def dispersion_series(
    daily: dict[str, list[DailyRow]],
    d: int,
    is_member=_ALWAYS,
    exclude: frozenset[str] = EXCLUDE,
) -> list[tuple[int, float]]:
    if d <= 0:
        return []

    ret_maps: dict[int, list[float]] = {}
    for sym, rows in daily.items():
        if sym in exclude:
            continue
        rows = _sorted_rows(rows)
        for i in range(d, len(rows)):
            cur = rows[i]
            prev = rows[i - d]
            if cur.ts_ms - prev.ts_ms != d * DAY_MS:
                continue
            if not is_member(sym, cur.ts_ms):
                continue
            if prev.close <= 0:
                continue
            ret_maps.setdefault(cur.ts_ms, []).append(cur.close / prev.close - 1.0)

    out: list[tuple[int, float]] = []
    for ts, returns in sorted(ret_maps.items()):
        if len(returns) < 2:
            continue
        out.append((ts, stdev(returns)))
    return out


def dispersion_regime_state(
    daily: dict[str, list[DailyRow]],
    btc: list[Candle],
    d: int,
    m_ma: int,
    window: int,
    p: float,
    is_member=_ALWAYS,
) -> list[tuple[int, str]]:
    disp = dispersion_series(daily, d, is_member=is_member)
    if not disp:
        return []

    disp_ts = [ts for ts, _ in disp]
    btc_closes = btc_daily_closes(btc, disp_ts)

    out: list[tuple[int, str]] = []
    for idx, (ts, dval) in enumerate(disp):
        if m_ma <= 0 or window <= 0:
            out.append((ts, "FLAT"))
            continue
        if idx < window:
            out.append((ts, "FLAT"))
            continue
        hist = [value for _, value in disp[idx - window:idx]]
        hist = sorted(hist)
        thr_idx = min(int(p * len(hist)), len(hist) - 1)
        thr = hist[thr_idx]
        if dval < thr:
            out.append((ts, "FLAT"))
            continue
        btc_hist = [btc_closes[t] for t in disp_ts[:idx] if t in btc_closes]
        if len(btc_hist) < m_ma:
            out.append((ts, "FLAT"))
            continue
        btc_ma = fmean(btc_hist[-m_ma:])
        price = btc_closes.get(ts)
        if price is None:
            out.append((ts, "FLAT"))
            continue
        if price > btc_ma:
            side = "LONG"
        elif price < btc_ma:
            side = "SHORT"
        else:
            side = "FLAT"
        out.append((ts, side))
    return out
