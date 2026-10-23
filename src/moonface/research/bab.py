# src/moonface/research/bab.py
"""Betting-against-beta / low-volatility cross-sectional long-short over a
USDT-perp universe.

Pre-registered construction (experiments/bab/PREREGISTRATION.md, frozen before
any universe data was seen): monthly top-N universe by trailing quote volume
with a listing-age floor; each week, estimate every member's trailing-60d beta
against the equal-weight universe index; long the bottom beta quintile, short
the top, each leg scaled by 1 / (mean leg beta) so the book is ex-ante
beta-neutral (Frazzini-Pedersen weighting); taker fees on turnover plus actual
funding accrual. Judged with the program's standard ladder.

This is a *second-moment* cross-sectional sort, signed and economically
independent of the already-rejected momentum/carry families (xsection v1). It
reuses build_universe and gate_construction from xsection unchanged; only the
beta signal and the beta-neutral leg weighting are new. Pure; network IO lives
in moonface.research.universe_data and the CLI (tools/bab.py)."""
from __future__ import annotations

from moonface.research.universe_data import DailyRow
from moonface.research.xsection import _month, build_universe

_DAY_MS = 86_400_000
BETA_MIN_POINTS = 20  # min overlapping daily returns to estimate a beta


def return_series(closes: dict[int, DailyRow],
                  calendar: list[int]) -> dict[int, float]:
    """One-day returns keyed by calendar day: r[t] = close[t]/close[t_prev]-1
    where t_prev is the immediately preceding calendar day. Days missing
    either close are absent — no synthetic multi-day return spans a gap."""
    out: dict[int, float] = {}
    for i in range(1, len(calendar)):
        t, p = calendar[i], calendar[i - 1]
        cur, prev = closes.get(t), closes.get(p)
        if cur is not None and prev is not None and prev.close != 0.0:
            out[t] = cur.close / prev.close - 1.0
    return out


def index_returns(rets: dict[str, dict[int, float]],
                  members_by_month: dict[tuple[int, int], list[str]],
                  calendar: list[int]) -> dict[int, float]:
    """Equal-weight mean return across the active month's universe members
    each day; days with no available member return are absent."""
    out: dict[int, float] = {}
    for t in calendar:
        members = members_by_month.get(_month(t), [])
        vals = [rets[s][t] for s in members if s in rets and t in rets[s]]
        if vals:
            out[t] = sum(vals) / len(vals)
    return out


def beta_signal(sym_ret: dict[int, float], idx_ret: dict[int, float], ts: int,
                lookback_days: int,
                min_points: int = BETA_MIN_POINTS) -> float | None:
    """OLS beta of the symbol's daily returns on the index over the
    `lookback_days` ending at ts (inclusive). None when fewer than min_points
    overlapping days, or the index has zero variance over the window."""
    lo = ts - lookback_days * _DAY_MS
    xs: list[float] = []
    ys: list[float] = []
    for t, ri in idx_ret.items():
        if lo < t <= ts and t in sym_ret:
            xs.append(ri)
            ys.append(sym_ret[t])
    if len(xs) < min_points:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0.0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var


def _rebalance(universe: list[str], rets: dict[str, dict[int, float]],
               idx_ret: dict[int, float], lookback_days: int, ts: int,
               k: int) -> dict[str, float]:
    """Beta-neutral long-low / short-high book for one rebalance day. Each leg
    is scaled by 1 / (mean leg beta) so ex-ante portfolio beta is ~0; an
    equal-weight neutral fallback covers a non-positive mean leg beta."""
    scored: list[tuple[float, str]] = []
    for sym in universe:
        b = beta_signal(rets.get(sym, {}), idx_ret, ts, lookback_days)
        if b is None:
            continue
        scored.append((b, sym))
    if len(scored) < 2 * k:
        return {}
    scored.sort(key=lambda t: (t[0], t[1]))
    lows, highs = scored[:k], scored[-k:]
    b_lo = sum(b for b, _ in lows) / k
    b_hi = sum(b for b, _ in highs) / k
    if b_lo > 0.0 and b_hi > 0.0:
        w_lo, w_hi = (1.0 / b_lo) / k, (1.0 / b_hi) / k
    else:  # degenerate betas: fall back to plain dollar-neutral legs
        w_lo = w_hi = 1.0 / k
    book = {sym: w_lo for _, sym in lows}
    book.update({sym: -w_hi for _, sym in highs})
    return book


def simulate(daily: dict[str, list[DailyRow]],
             funding: dict[str, dict[int, float]],
             lookback_days: int, start_ms: int, end_ms: int, top_n: int,
             quintile: int, rebalance_days: int, fee: float,
             min_history_days: int, vol_days: int) -> list[tuple[int, float]]:
    """Daily (ts, portfolio return) series. Betas estimated at day t set
    weights that earn from t+1 (no lookahead); fees hit the rebalance day's
    return; longs pay positive funding, shorts receive it."""
    calendar = sorted({r.ts_ms for rows in daily.values() for r in rows
                       if start_ms <= r.ts_ms < end_ms})
    closes = {sym: {r.ts_ms: r for r in rows} for sym, rows in daily.items()}
    rets = {sym: return_series(c, calendar) for sym, c in closes.items()}
    members_by_month: dict[tuple[int, int], list[str]] = {}
    for t in calendar:
        m = _month(t)
        if m not in members_by_month:
            members_by_month[m] = build_universe(
                daily, t, top_n, min_history_days, vol_days)
    idx_ret = index_returns(rets, members_by_month, calendar)
    k = max(1, top_n // quintile)
    weights: dict[str, float] = {}
    out: list[tuple[int, float]] = []
    for i in range(1, len(calendar)):
        ts = calendar[i]
        ret = 0.0
        for sym, w in weights.items():
            r = rets[sym].get(ts)
            if r is not None:
                ret += w * r
            ret -= w * funding.get(sym, {}).get(ts, 0.0)
        if (i - 1) % rebalance_days == 0:
            universe = members_by_month[_month(ts)]
            new = _rebalance(universe, rets, idx_ret, lookback_days, ts, k)
            turnover = sum(abs(new.get(s, 0.0) - weights.get(s, 0.0))
                           for s in set(new) | set(weights))
            ret -= fee * turnover
            weights = new
        out.append((ts, ret))
    return out
