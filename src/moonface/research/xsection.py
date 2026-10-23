# src/moonface/research/xsection.py
"""Cross-sectional long-short portfolio over a USDT-perp universe.

Pre-registered construction (docs/findings/BACKLOG.md item 2, frozen before any
universe data was seen): monthly top-N universe by trailing quote volume with
a listing-age floor, weekly rebalance, equal-weight quintile long-short,
taker fees on turnover plus actual funding accrual. Judged with the program's
standard gates: screen / holdout MAR + drawdown budget / DSR / lockbox tail.

Everything here is pure; network IO lives in moonface.research.universe_data
and the CLI (tools/xsection.py) wires them together."""
from __future__ import annotations

import datetime as dt

from moonface.research.universe_data import DailyRow
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                      SCREEN_FRACTION)
from moonface.core.metrics import EquitySummary, equity_summary

_DAY_MS = 86_400_000
SCREEN_MIN_DAYS = 60
LOCKBOX_MIN_DAYS = 30


def build_universe(daily: dict[str, list[DailyRow]], asof: int,
                   top_n: int, min_history_days: int,
                   vol_days: int) -> list[str]:
    """Top-N symbols by mean quote volume over (asof - vol_days, asof],
    requiring a listing age of at least min_history_days. Volume-descending."""
    floor_ts = asof - min_history_days * _DAY_MS
    window_start = asof - vol_days * _DAY_MS
    ranked: list[tuple[float, str]] = []
    for sym, rows in daily.items():
        if not rows or rows[0].ts_ms > floor_ts:
            continue
        vols = [r.quote_volume for r in rows
                if window_start < r.ts_ms <= asof]
        if not vols:
            continue
        ranked.append((sum(vols) / len(vols), sym))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [sym for _, sym in ranked[:top_n]]


def momentum_signal(closes: dict[int, DailyRow], ts: int,
                    days: int) -> float | None:
    """Trailing `days`-day return ending at ts; None when either close is
    missing (symbol excluded from that week's ranking)."""
    now, then = closes.get(ts), closes.get(ts - days * _DAY_MS)
    if now is None or then is None or then.close == 0.0:
        return None
    return now.close / then.close - 1.0


def carry_signal(funding_day: dict[int, float], ts: int, days: int) -> float:
    """Mean daily funding over the `days` days ending at ts. Missing days
    count as zero — an unfunded day is genuinely zero carry, not a data hole."""
    window = [funding_day.get(ts - i * _DAY_MS, 0.0) for i in range(days)]
    return sum(window) / days


def _month(ts: int) -> tuple[int, int]:
    d = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)
    return d.year, d.month


def simulate(daily: dict[str, list[DailyRow]],
             funding: dict[str, dict[int, float]],
             kind: str, days: int, start_ms: int, end_ms: int,
             top_n: int, quintile: int, rebalance_days: int, fee: float,
             min_history_days: int, vol_days: int) -> list[tuple[int, float]]:
    """Daily (ts, portfolio return) series. Signals at day t set weights that
    earn from t+1 (no lookahead); fees hit the rebalance day's return; longs
    pay positive funding. funding values are per-symbol daily rate sums."""
    calendar = sorted({r.ts_ms for rows in daily.values() for r in rows
                       if start_ms <= r.ts_ms < end_ms})
    closes = {sym: {r.ts_ms: r for r in rows} for sym, rows in daily.items()}
    k = max(1, top_n // quintile)
    weights: dict[str, float] = {}
    universe: list[str] = []
    built_month: tuple[int, int] | None = None
    out: list[tuple[int, float]] = []
    for i in range(1, len(calendar)):
        ts, prev_ts = calendar[i], calendar[i - 1]
        ret = 0.0
        for sym, w in weights.items():
            cur = closes[sym].get(ts)
            prev = closes[sym].get(prev_ts)
            if cur is not None and prev is not None and prev.close != 0.0:
                ret += w * (cur.close / prev.close - 1.0)
            ret -= w * funding.get(sym, {}).get(ts, 0.0)
        if (i - 1) % rebalance_days == 0:
            if built_month != _month(ts):
                universe = build_universe(daily, ts, top_n,
                                          min_history_days, vol_days)
                built_month = _month(ts)
            new = _rebalance(universe, closes, funding, kind, days, ts, k)
            turnover = sum(abs(new.get(s, 0.0) - weights.get(s, 0.0))
                           for s in set(new) | set(weights))
            ret -= fee * turnover
            weights = new
        out.append((ts, ret))
    return out


def _rebalance(universe: list[str], closes: dict[str, dict[int, DailyRow]],
               funding: dict[str, dict[int, float]], kind: str, days: int,
               ts: int, k: int) -> dict[str, float]:
    scored: list[tuple[float, str]] = []
    for sym in universe:
        if kind == "momentum":
            sig = momentum_signal(closes[sym], ts, days)
            if sig is None:
                continue
        else:
            if closes[sym].get(ts) is None:  # must be tradeable today
                continue
            sig = carry_signal(funding.get(sym, {}), ts, days)
        scored.append((sig, sym))
    if len(scored) < 2 * k:
        return {}
    scored.sort(key=lambda t: (t[0], t[1]))
    if kind == "momentum":  # long winners, short losers
        longs, shorts = scored[-k:], scored[:k]
    else:  # carry: long low funding, short high funding — collect both legs
        longs, shorts = scored[:k], scored[-k:]
    w = 1.0 / k
    book = {sym: w for _, sym in longs}
    book.update({sym: -w for _, sym in shorts})
    return book


def _summary(returns: list[float]) -> EquitySummary:
    # atr_frac=1.0 with fraction=1.0 makes equity_summary compound the raw
    # daily returns (f_eff = min(1, 5*1) = 1), reusing the program's metric.
    return equity_summary([(r, 1.0) for r in returns], 1.0)


def gate_construction(returns: list[float], fence_idx: int) -> dict:
    """Stage metrics for one construction's daily-return series. The tail
    segment is summarized for the report but only consulted (stage 4) for
    constructions that already cleared stages 1-3 — the constructions are
    fully pre-registered, so there is no selection loop on the tail."""
    research, tail = returns[:fence_idx], returns[fence_idx:]
    split = int(len(research) * SCREEN_FRACTION)
    screen, holdout = research[:split], research[split:]
    screen_mean = sum(screen) / len(screen) if screen else 0.0
    hold = _summary(holdout)
    full = _summary(research)
    tail_s = _summary(tail)
    return {
        "screen_days": len(screen),
        "screen_mean": round(screen_mean, 8),
        "stage1_pass": (len(screen) >= SCREEN_MIN_DAYS and screen_mean > 0.0),
        "holdout_mar": hold.mar,
        "holdout_drawdown": hold.max_drawdown,
        "stage2_pass": (hold.mar > 0.0
                        and hold.max_drawdown >= DRAWDOWN_BUDGET),
        "research_days": full.trade_count,
        "research_net": full.net_return,
        "research_mar": full.mar,
        "research_sharpe": full.sharpe,
        "research_skew": full.skew,
        "research_kurtosis": full.kurtosis,
        "tail_days": tail_s.trade_count,
        "tail_net": tail_s.net_return,
        "tail_mar": tail_s.mar,
        "tail_drawdown": tail_s.max_drawdown,
        "stage4_pass": (tail_s.mar >= LOCKBOX_MIN_MAR
                        and tail_s.trade_count >= LOCKBOX_MIN_DAYS
                        and tail_s.max_drawdown >= DRAWDOWN_BUDGET),
    }
