# src/moonface/research/liqprem.py
"""Cross-sectional Amihud illiquidity premium over a USDT-perp universe.

Pre-registered construction (experiments/liqprem/PREREGISTRATION.md, frozen
before any universe data was seen): a minimum-viability universe (listed >= 1
year AND trailing-30d MEDIAN daily dollar volume >= $1M) instead of top-N by
volume, because a top-N universe truncates exactly the illiquid tail the
hypothesis is about; Amihud illiquidity = trailing-30d mean of |daily return| /
daily dollar volume; long the most-illiquid quintile, short the most-liquid
quintile, each leg beta-neutral scaled; weekly rebalance; punitive ASYMMETRIC
costs (25 bps/side illiquid leg, 5 bps/side liquid leg) plus actual funding
accrual.

The standing *level* premium for liquidity provision — distinct from the dead
momentum/carry (xsection, first moment), BAB (bab, second moment) and residual
reversal (resrev, short-horizon liquidity *demand*) families. Beta machinery is
reused from bab and the ladder from xsection; only the signal, the viability
universe and the asymmetric cost model are new. Pure; network IO lives in
moonface.research.universe_data and the CLI (tools/liqprem.py)."""
from __future__ import annotations

from statistics import median

from moonface.research.universe_data import DailyRow
from moonface.research.bab import beta_signal, index_returns, return_series
from moonface.research.xsection import _month

_DAY_MS = 86_400_000
MIN_AMIHUD_POINTS = 20  # min usable days to estimate an Amihud score
AMIHUD_DAYS = 30        # trailing window for the illiquidity mean


def amihud_signal(sym_ret: dict[int, float], closes: dict[int, DailyRow],
                  ts: int, days: int,
                  min_points: int = MIN_AMIHUD_POINTS) -> float | None:
    """Trailing `days`-day mean of |daily return| / daily dollar volume,
    ending at ts (inclusive). Days with zero or missing dollar volume are
    dropped rather than treated as infinitely illiquid. None when fewer than
    min_points usable days — the symbol leaves that day's ranking."""
    lo = ts - days * _DAY_MS
    vals: list[float] = []
    for t, r in sym_ret.items():
        if not (lo < t <= ts):
            continue
        row = closes.get(t)
        if row is None or row.quote_volume <= 0.0:
            continue
        vals.append(abs(r) / row.quote_volume)
    if len(vals) < min_points:
        return None
    return sum(vals) / len(vals)


def build_viability_universe(daily: dict[str, list[DailyRow]], asof: int,
                             min_history_days: int, vol_days: int,
                             min_median_dollar_vol: float) -> list[str]:
    """Every symbol that is listed at least min_history_days before asof AND
    whose MEDIAN daily dollar volume over (asof - vol_days, asof] clears
    min_median_dollar_vol. Alphabetical, NOT volume-ranked: a top-N universe
    would truncate the illiquid tail this hypothesis is about. Median rather
    than mean so a single listing-pump print cannot buy admission."""
    floor_ts = asof - min_history_days * _DAY_MS
    window_start = asof - vol_days * _DAY_MS
    out: list[str] = []
    for sym, rows in daily.items():
        if not rows or rows[0].ts_ms > floor_ts:
            continue
        vols = [r.quote_volume for r in rows
                if window_start < r.ts_ms <= asof]
        if not vols or median(vols) < min_median_dollar_vol:
            continue
        out.append(sym)
    out.sort()
    return out


def _rebalance(universe: list[str], rets: dict[str, dict[int, float]],
               closes: dict[str, dict[int, DailyRow]],
               idx_ret: dict[int, float], ts: int, quintile: int,
               lookback_days: int, amihud_days: int) -> dict[str, float]:
    """Beta-neutral long-illiquid / short-liquid book for one rebalance day.

    Leg size k is derived from the SCORED count, not from a fixed top_n: the
    viability universe varies in size month to month, so a fixed k would
    silently change the quintile definition as the universe grows."""
    scored: list[tuple[float, float, str]] = []
    for sym in universe:
        b = beta_signal(rets.get(sym, {}), idx_ret, ts, lookback_days)
        if b is None:
            continue
        a = amihud_signal(rets.get(sym, {}), closes.get(sym, {}), ts,
                          amihud_days)
        if a is None:
            continue
        scored.append((a, b, sym))
    k = max(1, len(scored) // quintile)
    if len(scored) < 2 * k:
        return {}
    scored.sort(key=lambda t: (t[0], t[2]))
    liquid, illiquid = scored[:k], scored[-k:]  # low Amihud == most liquid
    b_il = sum(b for _, b, _ in illiquid) / k
    b_li = sum(b for _, b, _ in liquid) / k
    if b_il > 0.0 and b_li > 0.0:
        w_il, w_li = (1.0 / b_il) / k, (1.0 / b_li) / k
    else:
        w_il = w_li = 1.0 / k
    book = {sym: w_il for _, _, sym in illiquid}
    book.update({sym: -w_li for _, _, sym in liquid})
    return book


def _leg_fee(sym: str, new: dict[str, float], old: dict[str, float],
             fee_illiquid: float, fee_liquid: float) -> float:
    """The cost rate for one symbol's turnover. A symbol is priced by the leg
    it is entering; if it is absent from the new book it is priced by the leg
    it is leaving. Long == illiquid leg == the punitive rate."""
    w = new.get(sym, 0.0)
    if w == 0.0:
        w = old.get(sym, 0.0)
    return fee_illiquid if w > 0.0 else fee_liquid


def simulate(daily: dict[str, list[DailyRow]],
             funding: dict[str, dict[int, float]],
             start_ms: int, end_ms: int, quintile: int, rebalance_days: int,
             fee_illiquid: float, fee_liquid: float, min_history_days: int,
             vol_days: int, min_median_dollar_vol: float,
             lookback_days: int, amihud_days: int) -> list[tuple[int, float]]:
    """Daily (ts, portfolio return) series. Amihud scores at day t set weights
    that earn from t+1 (no lookahead); turnover costs hit the rebalance day's
    return at the PER-LEG rate; longs pay positive funding, shorts receive it."""
    calendar = sorted({r.ts_ms for rows in daily.values() for r in rows
                       if start_ms <= r.ts_ms < end_ms})
    closes = {sym: {r.ts_ms: r for r in rows} for sym, rows in daily.items()}
    rets = {sym: return_series(c, calendar) for sym, c in closes.items()}
    members_by_month: dict[tuple[int, int], list[str]] = {}
    for t in calendar:
        m = _month(t)
        if m not in members_by_month:
            members_by_month[m] = build_viability_universe(
                daily, t, min_history_days, vol_days, min_median_dollar_vol)
    idx_ret = index_returns(rets, members_by_month, calendar)
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
            new = _rebalance(universe, rets, closes, idx_ret, ts, quintile,
                             lookback_days, amihud_days)
            for sym in set(new) | set(weights):
                delta = abs(new.get(sym, 0.0) - weights.get(sym, 0.0))
                ret -= delta * _leg_fee(sym, new, weights,
                                        fee_illiquid, fee_liquid)
            weights = new
        out.append((ts, ret))
    return out
