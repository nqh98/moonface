from __future__ import annotations

import random
from dataclasses import dataclass

from moonface.core.metrics import Summary
from moonface.core.models import Candle
from moonface.kernel.bootstrap import iid_resample_randrange

# ~6 months of H1 candles reserved as an untouched out-of-sample tail.
DEFAULT_OOS_TAIL_BARS = 4380

REJECT = -1e9


@dataclass(frozen=True)
class GatedScore:
    valid: bool
    score: float          # OOS net R when valid, else REJECT
    train_net_r: float
    oos_net_r: float
    oos_trade_count: int
    max_drawdown_r: float
    reject_reason: str | None


def gated_score(
    train: Summary,
    oos: Summary,
    min_trades: int = 30,
    max_drawdown_r: float = 15.0,
) -> GatedScore:
    """Net-R objective gated on significance, drawdown, and OOS profitability."""
    worst_dd = min(train.max_drawdown_r, oos.max_drawdown_r)  # most negative
    reason: str | None = None
    if oos.trade_count < min_trades:
        reason = f"too few OOS trades ({oos.trade_count} < {min_trades})"
    elif abs(worst_dd) > max_drawdown_r:
        reason = f"max drawdown {abs(worst_dd):.2f}R exceeds {max_drawdown_r}R"
    elif oos.total_r <= 0:
        reason = f"OOS net R not positive ({oos.total_r:.2f})"
    valid = reason is None
    return GatedScore(
        valid=valid,
        score=oos.total_r if valid else REJECT,
        train_net_r=train.total_r,
        oos_net_r=oos.total_r,
        oos_trade_count=oos.trade_count,
        max_drawdown_r=round(worst_dd, 4),
        reject_reason=reason,
    )


def split_research_tail(
    h1: list[Candle],
    oos_tail_bars: int = DEFAULT_OOS_TAIL_BARS,
    warmup: int = 60,
    future_bars: int = 48,
) -> int:
    """Index where the locked OOS tail begins. Mirrors anchored_walk_forward's split.

    Raises if the tail leaves no research region to iterate on.
    """
    n = len(h1)
    if n - oos_tail_bars < warmup + future_bars:
        raise ValueError(
            f"tail of {oos_tail_bars} bars leaves no research region "
            f"(n={n}, warmup={warmup}, future_bars={future_bars})"
        )
    return max(warmup + future_bars, n - oos_tail_bars)

DD_CAP = 0.20
PERCENTILE = 95
RESAMPLES = 10_000
SEED = 12345
DEFAULT_F_GRID = [round(0.01 * i, 2) for i in range(1, 51)]  # 0.01 .. 0.50


@dataclass(frozen=True)
class EquityStats:
    terminal: float
    cagr: float | None
    max_drawdown_pct: float
    n_trades: int


def simulate_equity(
    rs: list[float],
    f: float,
    start: float = 1.0,
    span_days: float = 0.0,
) -> EquityStats:
    """Compound an ordered net-R stream at fixed fraction f: e *= (1 + f*r)."""
    equity = start
    peak = start
    max_dd = 0.0
    for r in rs:
        factor = 1.0 + f * r
        if factor <= 0.0:  # ruin: loss exceeds equity
            return EquityStats(terminal=0.0, cagr=None, max_drawdown_pct=100.0,
                               n_trades=len(rs))
        equity *= factor
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    cagr: float | None = None
    if span_days > 0 and equity > 0:
        cagr = round(equity ** (365.25 / span_days) - 1.0, 6)
    return EquityStats(terminal=round(equity, 6), cagr=cagr,
                       max_drawdown_pct=round(max_dd, 4), n_trades=len(rs))


def monte_carlo_drawdown(
    rs: list[float],
    f: float,
    percentile: float = 95,
    resamples: int = 10_000,
    seed: int = 12345,
) -> float:
    """IID bootstrap of max-drawdown-%; return the percentile-th value (nearest-rank)."""
    if not rs:
        return 0.0
    rng = random.Random(seed)
    dds: list[float] = []
    for _ in range(resamples):
        path = iid_resample_randrange(rng, rs)
        dds.append(simulate_equity(path, f).max_drawdown_pct)
    dds.sort()
    idx = min(len(dds) - 1, int(round(percentile / 100.0 * (len(dds) - 1))))
    return dds[idx]


@dataclass(frozen=True)
class FractionResult:
    f: float
    terminal: float
    mc_drawdown_pct: float
    hist_drawdown_pct: float
    capped: bool


def optimize_fraction(
    rs: list[float],
    dd_cap: float = DD_CAP,
    percentile: float = PERCENTILE,
    resamples: int = RESAMPLES,
    seed: int = SEED,
    f_grid: list[float] | None = None,
) -> FractionResult:
    """Grid-search f maximizing terminal equity subject to MC drawdown <= dd_cap."""
    if not 0.0 < dd_cap <= 1.0:
        raise ValueError(f"dd_cap must be in (0, 1], got {dd_cap}")
    if not 0.0 < percentile < 100.0:
        raise ValueError(f"percentile must be in (0, 100), got {percentile}")
    if resamples <= 0:
        raise ValueError(f"resamples must be positive, got {resamples}")
    grid = DEFAULT_F_GRID if f_grid is None else list(f_grid)
    if not grid:
        raise ValueError("f_grid must be non-empty")

    best = FractionResult(f=0.0, terminal=1.0, mc_drawdown_pct=0.0,
                          hist_drawdown_pct=0.0, capped=False)
    if not rs:
        return best
    cap_pct = dd_cap * 100.0
    for f in grid:
        mc = monte_carlo_drawdown(rs, f, percentile, resamples, seed)
        if mc > cap_pct:
            continue
        stats = simulate_equity(rs, f)
        if stats.terminal <= 1.0 or stats.terminal <= best.terminal:
            continue
        best = FractionResult(f=f, terminal=stats.terminal, mc_drawdown_pct=mc,
                              hist_drawdown_pct=stats.max_drawdown_pct, capped=True)
    return best


@dataclass(frozen=True)
class SizingReport:
    chosen_f: float
    research: EquityStats
    tail: EquityStats
    research_mc_drawdown_pct: float
    tail_mc_drawdown_pct: float
    dd_cap: float
    percentile: float
    reject_reason: str | None


def size_report(
    research_rs: list[float],
    tail_rs: list[float],
    *,
    dd_cap: float = DD_CAP,
    percentile: float = PERCENTILE,
    resamples: int = RESAMPLES,
    seed: int = SEED,
    f_grid: list[float] | None = None,
    research_span_days: float = 0.0,
    tail_span_days: float = 0.0,
) -> SizingReport:
    """Fit f on research_rs, apply the pre-committed f to both research and tail."""
    if not research_rs:
        empty = EquityStats(terminal=1.0, cagr=None, max_drawdown_pct=0.0, n_trades=0)
        return SizingReport(chosen_f=0.0, research=empty, tail=empty,
                            research_mc_drawdown_pct=0.0, tail_mc_drawdown_pct=0.0,
                            dd_cap=dd_cap, percentile=percentile,
                            reject_reason="no research trades to size")
    fr = optimize_fraction(research_rs, dd_cap, percentile, resamples, seed, f_grid)
    f = fr.f
    research = simulate_equity(research_rs, f, span_days=research_span_days)
    research_mc = monte_carlo_drawdown(research_rs, f, percentile, resamples, seed)
    tail = simulate_equity(tail_rs, f, span_days=tail_span_days)
    tail_mc = monte_carlo_drawdown(tail_rs, f, percentile, resamples, seed) if tail_rs else 0.0
    reason = None if fr.capped else "no drawdown-capped fraction yields positive growth"
    return SizingReport(chosen_f=f, research=research, tail=tail,
                        research_mc_drawdown_pct=research_mc, tail_mc_drawdown_pct=tail_mc,
                        dd_cap=dd_cap, percentile=percentile, reject_reason=reason)
