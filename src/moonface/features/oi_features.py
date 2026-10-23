# src/moonface/research/oibuild_study.py
"""Pooled cross-asset test of the OI-build mechanism — pure statistics.

Design frozen in experiments/oibuild_study/PREREGISTRATION.md. This module
deliberately contains no strategy machinery: events come verbatim from
make_oi_build_momentum, outcomes are gross directional forward returns, and
the verdict is the pre-registered tripartite rule. Each asset is one unit of
evidence; raw events are never pooled across assets."""
from __future__ import annotations

import math
from statistics import fmean

from moonface.research.universe_data import DailyRow

_DAY_MS = 86_400_000

MIN_EVENTS_PER_ASSET = 10
MIN_ASSETS = 8
SIGN_ALPHA = 0.05
STOUFFER_CRIT = 1.645


def select_universe(daily: dict[str, list[DailyRow]], window_start: int,
                    exclude: set[str], top_k: int, vol_days: int,
                    min_history_days: int) -> list[str]:
    """Candidate queue ranked by mean daily quote volume over the vol_days
    ending at window_start — information available at window start only —
    with a listing-age floor. The discovery set is excluded by `exclude`."""
    floor_ts = window_start - min_history_days * _DAY_MS
    vol_start = window_start - vol_days * _DAY_MS
    ranked: list[tuple[float, str]] = []
    for sym, rows in daily.items():
        if sym in exclude or not rows or rows[0].ts_ms > floor_ts:
            continue
        vols = [r.quote_volume for r in rows
                if vol_start < r.ts_ms <= window_start]
        if not vols:
            continue
        ranked.append((fmean(vols), sym))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [sym for _, sym in ranked[:top_k]]


def fresh_coverage(candles, points: list[tuple[int, float]],
                   max_age_ms: int = _DAY_MS) -> float:
    """Fraction of bars whose as-of metrics snapshot is at most max_age_ms
    old. The bundle's non-None coverage is blind to a feed that dies early
    (carry-forward keeps it non-None); staleness is the honest gate here."""
    if not candles:
        return 0.0
    ts_points = sorted(t for t, _ in points)
    fresh = 0
    j = 0
    last: int | None = None
    for c in candles:
        while j < len(ts_points) and ts_points[j] <= c.timestamp_ms:
            last = ts_points[j]
            j += 1
        if last is not None and c.timestamp_ms - last <= max_age_ms:
            fresh += 1
    return fresh / len(candles)


def nonoverlap(events: list[tuple[int, str]], h: int) -> list[tuple[int, str]]:
    """Drop events within h bars of the previously accepted one: overlapping
    forward windows are serially dependent and would overstate n."""
    out: list[tuple[int, str]] = []
    last = -h - 1
    for i, side in sorted(events):
        if i - last >= h:
            out.append((i, side))
            last = i
    return out


def event_returns(closes: list[float], events: list[tuple[int, str]],
                  h: int) -> list[float]:
    """Gross directional simple return sign * (close[i+h]/close[i] - 1) per
    event; events without h bars of future are discarded."""
    out: list[float] = []
    for i, side in events:
        if i + h >= len(closes) or closes[i] == 0.0:
            continue
        r = closes[i + h] / closes[i] - 1.0
        out.append(r if side == "LONG" else -r)
    return out


def asset_stats(returns: list[float]) -> dict:
    n = len(returns)
    if n == 0:
        return {"n": 0, "mean": 0.0, "t": 0.0}
    mean = fmean(returns)
    if n < 2:
        return {"n": n, "mean": mean, "t": 0.0}
    var = sum((x - mean) ** 2 for x in returns) / (n - 1)
    t = 0.0 if var <= 0.0 else mean / math.sqrt(var) * math.sqrt(n)
    return {"n": n, "mean": mean, "t": t}


def binom_p_geq(k: int, m: int) -> float:
    """Exact one-sided P(Bin(m, 1/2) >= k)."""
    return sum(math.comb(m, j) for j in range(k, m + 1)) / 2 ** m


def stouffer(ts: list[float]) -> float:
    if not ts:
        return 0.0
    return sum(ts) / math.sqrt(len(ts))


def verdict_from(stats: list[dict], min_assets: int = MIN_ASSETS) -> dict:
    """The pre-registered tripartite verdict over evaluable per-asset stats."""
    m = len(stats)
    base = {"m_assets": m, "p_sign": None, "stouffer_z": None,
            "pooled_mean": None, "reason": ""}
    if m < min_assets:
        return {**base, "verdict": "inconclusive",
                "reason": f"insufficient evaluable assets ({m} < {min_assets})"}
    k = sum(1 for s in stats if s["mean"] > 0)
    p_sign = binom_p_geq(k, m)
    z = stouffer([s["t"] for s in stats])
    pooled_mean = fmean([s["mean"] for s in stats])
    base.update(k_positive=k, p_sign=p_sign, stouffer_z=z,
                pooled_mean=pooled_mean)
    if p_sign <= SIGN_ALPHA and z >= STOUFFER_CRIT:
        return {**base, "verdict": "mechanism_exists",
                "reason": f"breadth p={p_sign:.4g} and magnitude Z={z:.2f}"
                          " both clear the frozen criteria"}
    if pooled_mean <= 0.0:
        return {**base, "verdict": "mechanism_does_not_exist",
                "reason": "equal-weight pooled mean directional return is"
                          f" non-positive ({pooled_mean:.6f}) on fresh assets"}
    return {**base, "verdict": "inconclusive",
            "reason": f"pooled mean positive ({pooled_mean:.6f}) but"
                      f" p={p_sign:.4g} / Z={z:.2f} miss the frozen criteria"}
