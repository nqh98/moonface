"""Rolling walk-forward harness. Train strictly precedes test; the verdict
aggregates TEST-window results only."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.metrics import Summary, summarize_r
from moonface.research.trend_sim import TrendParams, simulate_donchian


@dataclass(frozen=True)
class WalkResult:
    test_summaries: list[Summary]
    aggregated: Summary
    chosen_params: list[TrendParams]


def _patch(p: TrendParams, **kw) -> TrendParams:
    return TrendParams(**{**p.__dict__, **kw})


def walk_forward(candles: list[Candle], funding_points,
                 param_grid: list[TrendParams], train_bars: int, test_bars: int,
                 step_bars: int, base_params: TrendParams | None = None) -> WalkResult:
    """For each fixed-length (train, test) window pair, pick the param with the best train
    expectancy, then evaluate it on the untouched test window. Aggregate test R."""
    test_rs: list[float] = []
    summaries: list[Summary] = []
    chosen: list[TrendParams] = []
    start = train_bars
    n = len(candles)
    while start + test_bars <= n:
        train_lo, train_hi = start - train_bars, start
        train = candles[train_lo:train_hi]
        test_lo, test_hi = start, start + test_bars
        test = candles[test_lo:test_hi]
        fund_test = _window_funding(funding_points, candles, test_lo, test_hi)
        best = None
        best_exp = float("-inf")
        for p in param_grid:
            rs = [t.r_multiple for t in simulate_donchian(train, p,
                                                          _window_funding(funding_points, candles,
                                                                          train_lo, train_hi))]
            exp = summarize_r(rs).expectancy_r
            if exp > best_exp:
                best_exp, best = exp, p
        if best is None:
            best = param_grid[0]
        chosen.append(best)
        rs = [t.r_multiple for t in simulate_donchian(test, best, fund_test)]
        s = summarize_r(rs)
        summaries.append(s)
        test_rs.extend(rs)
        start += step_bars
    return WalkResult(test_summaries=summaries, aggregated=summarize_r(test_rs),
                      chosen_params=chosen)


def _window_funding(funding_points, candles, lo, hi):
    """Slice the funding series to the window [lo, hi) by timestamp."""
    if not funding_points:
        return None
    lo_ms = candles[lo].timestamp_ms
    hi_ms = candles[hi - 1].timestamp_ms
    return [(t, r) for t, r in funding_points if lo_ms <= t <= hi_ms]
