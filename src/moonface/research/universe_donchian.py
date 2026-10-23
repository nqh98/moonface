"""Universe-expansion Donchian domain (spec 2026-07-02).

The frozen trend_sim.simulate_donchian engine run on a dynamic top-5 altcoin
universe selected by abnormal 24h quote-volume expansion. The engine is byte-
frozen; the only new code is (a) a point-in-time screener [this task], (b) a
mark-to-market portfolio simulator [Task 2], and (c) dominance evaluators that
drive the ladder against a static-basket control [Task 3]. Pure functions only;
network IO + the Store live in universe_donchian_runner."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from moonface.core.metrics import (COST_FRACTION,
                                          equity_summary_from_returns, summarize_r)
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                       LOCKBOX_MIN_TRADES, SCREEN_FRACTION,
                                       SCREEN_MIN_TRADES)
from moonface.kernel.spec import HypothesisSpec
from moonface.research.universe_data import DailyRow

DOMAIN = "universe_donchian"
_DAY_MS = 86_400_000
N_TRIALS = 4
GROSS = 1.0
REBALANCE_DAYS = 7

# Excluded from the alt universe: the efficient majors + fiat/stable quote bases.
_EXCLUDE_BASES = {"BTC", "ETH", "USDC", "BUSD", "FDUSD", "TUSD", "EUR", "GBP",
                  "AEUR", "EURI", "XUSD", "USD1"}


def is_alt_perp(symbol: str) -> bool:
    """A genuine USDT alt perp: ends in USDT, base is not a major/stable, and it
    is not a dated future (those carry an underscore)."""
    if not symbol.endswith("USDT") or "_" in symbol:
        return False
    base = symbol[:-4]
    return len(base) >= 1 and base not in _EXCLUDE_BASES


def _window(rows, asof, lookback_days, include_asof):
    hi = asof if include_asof else asof - 1
    return [r.quote_volume for r in rows
            if asof - lookback_days * _DAY_MS < r.ts_ms <= hi]


def expansion_ratio(rows: list[DailyRow], asof: int,
                    lookback_days: int) -> float | None:
    """quote_volume[asof] / median(quote_volume over the trailing lookback window,
    excluding asof). None when the asof day or <2 prior days are absent."""
    prior = _window(rows, asof, lookback_days, include_asof=False)
    today = [r.quote_volume for r in rows if r.ts_ms == asof]
    if len(prior) < 2 or not today:
        return None
    m = median(prior)
    return None if m <= 0 else today[0] / m


def expansion_zscore(rows: list[DailyRow], asof: int,
                     lookback_days: int) -> float | None:
    """z-score of today's quote volume vs the trailing window (excluding asof)."""
    prior = _window(rows, asof, lookback_days, include_asof=False)
    today = [r.quote_volume for r in rows if r.ts_ms == asof]
    if len(prior) < 2 or not today:
        return None
    mean = sum(prior) / len(prior)
    var = sum((v - mean) ** 2 for v in prior) / (len(prior) - 1)
    return None if var <= 0 else (today[0] - mean) / var ** 0.5


def _qualifies(rows, asof, min_liquidity_usd, min_age_days, lookback_days):
    """Liquidity + listing-age floor (point-in-time: only data up to and including asof)."""
    if not rows or rows[0].ts_ms > asof - min_age_days * _DAY_MS:
        return False
    vols = _window(rows, asof, lookback_days, include_asof=True)
    return bool(vols) and sum(vols) / len(vols) >= min_liquidity_usd


def screen_universe(daily: dict[str, list[DailyRow]], asof: int,
                    cfg: dict) -> list[str]:
    """Eligible symbols at asof per cfg.
    cfg: top_n, lookback_days, metric ('ratio'|'zscore'), min_liquidity_usd,
    min_age_days, rank ('expansion'|'static'). rank='static' returns ALL
    qualifiers sorted (the control): no expansion ranking, no top_n cut."""
    metric_fn = (expansion_ratio if cfg.get("metric", "ratio") == "ratio"
                 else expansion_zscore)
    qualifiers = [s for s, rows in daily.items()
                  if _qualifies(rows, asof, cfg["min_liquidity_usd"],
                                cfg["min_age_days"], cfg["lookback_days"])]
    if cfg.get("rank", "expansion") == "static":
        return sorted(qualifiers)
    scored = []
    for s in qualifiers:
        score = metric_fn(daily[s], asof, cfg["lookback_days"])
        if score is not None:
            scored.append((score, s))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [s for _, s in scored[: cfg["top_n"]]]


def _screen_at(daily, asof, cfg):
    members = screen_universe(daily, asof, cfg)
    n = len(members) if cfg.get("rank", "expansion") == "static" else cfg["top_n"]
    return members, n


def build_membership(daily: dict[str, list[DailyRow]], calendar: list[int],
                     cfg: dict, rebalance_days: int = REBALANCE_DAYS
                     ) -> tuple[dict[int, frozenset[str]], dict[int, int]]:
    """Weekly membership + intended book-size schedule, keyed by every day in
    calendar. A screen computed at boundary day b is applied to days STRICTLY
    AFTER b (so day-i membership reflects a screen built on or before day i-1:
    no same-day look-ahead), mirroring xsection.simulate's 'signals at t earn
    from t+1' rule. Returns (membership, book_size) dicts over the calendar."""
    if not calendar:
        return {}, {}
    step = max(1, rebalance_days)
    screens: dict[int, tuple[list[str], int]] = {}
    for boundary in range(0, len(calendar), step):
        screens[boundary] = _screen_at(daily, calendar[boundary], cfg)
    membership: dict[int, frozenset[str]] = {}
    book_size: dict[int, int] = {}
    for i, ts in enumerate(calendar):
        # most recent boundary strictly before i (day 0's own screen only at i==0)
        b = 0 if i == 0 else ((i - 1) // step) * step
        members, n = screens[b]
        membership[ts] = frozenset(members)
        book_size[ts] = n
    return membership, book_size


@dataclass(frozen=True)
class Position:
    """A held Donchian position in daily-day space (engine trade mapped to UTC
    midnight entry/exit days). side is 'BUY' (long) or 'SELL' (short)."""
    side: str
    entry_day: int
    exit_day: int
    r_multiple: float


def _is_long(side: str) -> bool:
    return side == "BUY"


def simulate_portfolio(calendar: list[int],
                       membership: dict[int, frozenset[str]],
                       book_size: dict[int, int],
                       positions: dict[str, list[Position]],
                       daily_close: dict[str, dict[int, float]],
                       daily_funding: dict[str, dict[int, float]],
                       gross: float = GROSS,
                       cost: float = COST_FRACTION) -> list[float]:
    """Daily mark-to-market portfolio returns aligned to `calendar`
    (returns[0] == 0.0; returns[i] is the return INTO calendar[i]).

    A position deploys capital only if its symbol was eligible for a NEW entry
    on its entry day (sym in membership[entry_day]). It then earns the symbol's
    daily close-to-close return over (entry_day, exit_day] (entry day's move is
    not claimed — no look-ahead), minus funding (long pays +rate, short
    receives) and minus a one-way cost (cost/2) on the first held day (entry)
    and on the exit day. f_slot = gross / book_size[entry_day], fixed at entry."""
    one_way = cost / 2.0
    idx = {t: i for i, t in enumerate(calendar)}
    returns = [0.0] * len(calendar)
    for i in range(1, len(calendar)):
        prev_t, cur_t = calendar[i - 1], calendar[i]
        ret = 0.0
        # positions open over (entry, exit]: held on day i iff entry_index < i <= exit_index
        for sym, trades in positions.items():
            closes = daily_close.get(sym, {})
            fund = daily_funding.get(sym, {})
            c_prev, c_cur = closes.get(prev_t), closes.get(cur_t)
            if c_prev is None or c_prev == 0 or c_cur is None:
                continue
            price_ret = c_cur / c_prev - 1.0
            for pos in trades:
                ei = idx.get(pos.entry_day)
                xi = idx.get(pos.exit_day)
                if ei is None or xi is None or not (ei < i <= xi):
                    continue
                if sym not in membership.get(pos.entry_day, frozenset()):
                    continue
                n = book_size.get(pos.entry_day, 1)
                f_slot = gross / n if n > 0 else 0.0
                signed = price_ret if _is_long(pos.side) else -price_ret
                ret += f_slot * signed
                ret -= f_slot * fund.get(cur_t, 0.0) * (1 if _is_long(pos.side) else -1)
                if i == ei + 1:                 # entry cost on first held day
                    ret -= f_slot * one_way
                if i == xi:                     # exit cost on exit day
                    ret -= f_slot * one_way
        returns[i] = ret
    return returns


# ---------------------------------------------------------------------------
# Task 3: pre-registered treatment specs + static-basket control + BTC
# reference + dominance evaluators + stage gates. Pure functions; the engine
# params, filters and grids are FROZEN (spec 2026-07-02 §3) -- do not retune.
# ---------------------------------------------------------------------------
ENTRY_FAMILY = "volexp_donchian"
ENGINE_PARAMS = {"entry_n": 40, "trail_n": 20, "atr_period": 14, "k_stop": 2.0}
EXIT_NAME = "donchian_trail"

# Shared asset descriptor (universe, not a single symbol) + frozen filters.
_ASSET = {"exchange": "binanceusdm",
          "universe": "alt_perps_excl_btc_eth_stables", "timeframe": "4h"}
_BASE_FILTERS = {"min_liquidity_usd": 20e6, "min_age_days": 90, "lookback_days": 30}

# The 4 pre-registered treatment grids (spec §3). Only the screener varies.
_TREATMENT_GRIDS = [
    {"top_n": 5,  "lookback_days": 30, "metric": "ratio"},
    {"top_n": 5,  "lookback_days": 60, "metric": "ratio"},
    {"top_n": 10, "lookback_days": 30, "metric": "ratio"},
    {"top_n": 5,  "lookback_days": 30, "metric": "zscore"},
]


def _spec(params: dict) -> HypothesisSpec:
    cfg = {**_BASE_FILTERS, **params, "rank": "expansion", "long_only": False}
    return HypothesisSpec(
        domain=DOMAIN, version=1, asset=_ASSET,
        entry={"family": ENTRY_FAMILY, "params": cfg},
        exit={"name": EXIT_NAME, "params": ENGINE_PARAMS},
        fraction=GROSS)


def universe_donchian_specs() -> list[HypothesisSpec]:
    return [_spec(grid) for grid in _TREATMENT_GRIDS]


def control_for(spec: HypothesisSpec) -> HypothesisSpec:
    """The static broad-basket control: same filters + engine + fraction, but
    rank='static' (all qualifiers equal-weight, no expansion ranking)."""
    p = {**spec.entry["params"], "rank": "static"}
    return HypothesisSpec(
        domain=DOMAIN, version=1, asset=_ASSET,
        entry={"family": ENTRY_FAMILY, "params": p},
        exit={"name": EXIT_NAME, "params": ENGINE_PARAMS},
        fraction=GROSS)


def btc_reference_spec() -> HypothesisSpec:
    """Non-gating reference: the byte-identical deployed engine on BTC (long-only)."""
    return HypothesisSpec(
        domain=DOMAIN, version=1,
        asset={"exchange": "binanceusdm", "symbol": "BTCUSDT", "timeframe": "4h"},
        entry={"family": ENTRY_FAMILY,
               "params": {**_BASE_FILTERS, "rank": "static", "long_only": True}},
        exit={"name": EXIT_NAME, "params": ENGINE_PARAMS},
        fraction=GROSS)


def dominates(t_mar: float, t_sharpe: float,
              c_mar: float, c_sharpe: float) -> bool:
    return t_mar > c_mar and t_sharpe > c_sharpe


def _splits(returns: list[float], fence_idx: int, screen_fraction: float):
    research = returns[:fence_idx]
    cut = int(len(research) * screen_fraction)
    return research[:cut], research[cut:], returns[fence_idx:]


def evaluate_dominant(t_returns: list[float], c_returns: list[float],
                      pooled_trades: list[float], fence_idx: int,
                      screen_fraction: float = SCREEN_FRACTION) -> dict:
    """Stage-1/2 metrics for the treatment portfolio vs its control, all on the
    daily return series. Stage-1 trade stats come from `pooled_trades` (the
    engine's per-trade net R-multiples in the screen window)."""
    t_screen_ret, t_hold_ret, _ = _splits(t_returns, fence_idx, screen_fraction)
    _, c_hold_ret, _ = _splits(c_returns, fence_idx, screen_fraction)
    pooled = summarize_r(pooled_trades)
    t_hold = equity_summary_from_returns(t_hold_ret)
    c_hold = equity_summary_from_returns(c_hold_ret)
    t_full = equity_summary_from_returns(t_returns[:fence_idx])
    return {
        "screen_trades": pooled.trade_count,
        "screen_expectancy_r": pooled.expectancy_r,
        "holdout_treatment_mar": t_hold.mar,
        "holdout_treatment_dd": t_hold.max_drawdown,
        "holdout_treatment_sharpe": t_hold.sharpe,
        "holdout_control_mar": c_hold.mar,
        "holdout_control_sharpe": c_hold.sharpe,
        "holdout_dominance": dominates(t_hold.mar, t_hold.sharpe,
                                       c_hold.mar, c_hold.sharpe),
        "research_sharpe": t_full.sharpe,
        "research_skew": t_full.skew,
        "research_kurtosis": t_full.kurtosis,
        "research_trades": len(t_returns[:fence_idx]),
    }


def lockbox_dominant(t_returns: list[float], c_returns: list[float],
                     pooled_trades_tail: list[float]) -> dict:
    t_tail = equity_summary_from_returns(t_returns)
    c_tail = equity_summary_from_returns(c_returns)
    pooled = summarize_r(pooled_trades_tail)
    return {
        "tail_trades": pooled.trade_count,
        "tail_treatment_mar": t_tail.mar,
        "tail_treatment_dd": t_tail.max_drawdown,
        "tail_treatment_sharpe": t_tail.sharpe,
        "tail_control_mar": c_tail.mar,
        "tail_control_sharpe": c_tail.sharpe,
        "tail_dominance": dominates(t_tail.mar, t_tail.sharpe,
                                    c_tail.mar, c_tail.sharpe),
    }


def stage1_of(m: dict, min_trades: int = SCREEN_MIN_TRADES) -> bool:
    return m["screen_trades"] >= min_trades and m["screen_expectancy_r"] > 0.0


def stage2_of(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def stage4_of(m: dict, min_trades: int = LOCKBOX_MIN_TRADES) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= min_trades
            and m["tail_dominance"])
