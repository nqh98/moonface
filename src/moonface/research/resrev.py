# src/moonface/research/resrev.py
"""Cross-sectional short-term residual reversal over a USDT-perp universe.

Pre-registered construction (experiments/resrev/PREREGISTRATION.md, frozen
before any universe data was seen): monthly top-N universe by trailing quote
volume; each day, residual = ret − beta·index (trailing-60d beta vs the
equal-weight universe index); long the bottom residual decile (recent
idiosyncratic losers), short the top decile, each leg beta-neutral scaled; daily
rebalance, one-day hold; taker fees on turnover plus actual funding accrual.

A *mean-reversion* book on the idiosyncratic residual — distinct from the dead
momentum/carry (xsection) and BAB (bab) families. The beta machinery
(return_series, index_returns, beta_signal) and gate_construction are reused
unchanged; only the residual signal and residual-ranked weighting are new. Pure;
network IO lives in moonface.research.universe_data and the CLI (tools/resrev.py)."""
from __future__ import annotations

import math

from moonface.research.universe_data import DailyRow
from moonface.research.bab import beta_signal, index_returns, return_series
from moonface.research.xsection import _month, build_universe

_DAY_MS = 86_400_000


def residual_signal(sym_ret: dict[int, float], beta: float | None,
                    idx_ret: dict[int, float], ts: int) -> float | None:
    """ret_t − beta·index_t at the decision day; None when any input is
    missing (the symbol is dropped from that day's ranking)."""
    r, ix = sym_ret.get(ts), idx_ret.get(ts)
    if r is None or ix is None or beta is None:
        return None
    return r - beta * ix


def mean_z(returns: list[float]) -> tuple[float, float]:
    """(mean, Stouffer-style Z = mean / (std/sqrt(n))) for a return series.
    Zero variance: Z = +/-inf by the sign of the mean, 0 when the mean is 0."""
    n = len(returns)
    if n == 0:
        return 0.0, 0.0
    mean = sum(returns) / n
    if n < 2:
        return mean, math.copysign(math.inf, mean) if mean else 0.0
    var = sum((x - mean) ** 2 for x in returns) / (n - 1)
    if var == 0.0:
        return mean, (math.copysign(math.inf, mean) if mean else 0.0)
    return mean, mean / math.sqrt(var / n)


def _rebalance(universe: list[str], rets: dict[str, dict[int, float]],
               idx_ret: dict[int, float], lookback_days: int, ts: int,
               k: int) -> dict[str, float]:
    """Beta-neutral long-low-residual / short-high-residual book for one day."""
    scored: list[tuple[float, float, str]] = []
    for sym in universe:
        b = beta_signal(rets.get(sym, {}), idx_ret, ts, lookback_days)
        if b is None:
            continue
        resid = residual_signal(rets.get(sym, {}), b, idx_ret, ts)
        if resid is None:
            continue
        scored.append((resid, b, sym))
    if len(scored) < 2 * k:
        return {}
    scored.sort(key=lambda t: (t[0], t[2]))
    lows, highs = scored[:k], scored[-k:]  # low residual long, high short
    b_lo = sum(b for _, b, _ in lows) / k
    b_hi = sum(b for _, b, _ in highs) / k
    if b_lo > 0.0 and b_hi > 0.0:
        w_lo, w_hi = (1.0 / b_lo) / k, (1.0 / b_hi) / k
    else:
        w_lo = w_hi = 1.0 / k
    book = {sym: w_lo for _, _, sym in lows}
    book.update({sym: -w_hi for _, _, sym in highs})
    return book


def simulate(daily: dict[str, list[DailyRow]],
             funding: dict[str, dict[int, float]],
             lookback_days: int, start_ms: int, end_ms: int, top_n: int,
             decile: int, rebalance_days: int, fee: float,
             min_history_days: int, vol_days: int) -> list[tuple[int, float]]:
    """Daily (ts, portfolio return) series. Residuals at day t set weights that
    earn from t+1 (no lookahead); fees hit the rebalance day's return; longs pay
    positive funding, shorts receive it. `decile`=10 yields top_n//10 per leg."""
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
    k = max(1, top_n // decile)
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
