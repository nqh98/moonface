# src/moonface/research/fwd_analysis.py
"""Pre-cutoff trade-stream analysis for the funding_fade_fwd registration
draft: block-bootstrap CI, drawdown-budget bootstrap, time-under-water, and
the verdict-trigger power calculation. Stdlib only; deterministic via
random.Random(seed). All resampling is moving-block (block of completed
trades) to preserve short-range clustering; nothing is ever interpolated."""
from __future__ import annotations

import math
import random
from statistics import NormalDist, pstdev

from moonface.kernel.bootstrap import moving_block_resample

_DAY_MS = 86_400_000


def bootstrap_expectancy_ci(rs: list[float], resamples: int = 10_000,
                            block: int = 10, seed: int = 42,
                            alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI on mean R. Degenerate inputs (n<2 or zero variance)
    collapse to (mean, mean) so the caller sees the collapse instead of a
    fake interval (capitulation-lane lesson)."""
    if not rs:
        return (0.0, 0.0)
    if len(rs) < 2 or len(set(rs)) == 1:
        m = sum(rs) / len(rs)
        return (m, m)
    rng = random.Random(seed)
    means = sorted(
        sum(sample) / len(sample)
        for sample in (moving_block_resample(rng, rs, block)
                       for _ in range(resamples)))
    lo = means[int(alpha / 2 * resamples)]
    hi = means[min(resamples - 1, int((1 - alpha / 2) * resamples))]
    return (lo, hi)


def success_criterion(rs: list[float]) -> bool:
    """Conditions (i)+(ii) of the EDGE FOUND rule: 95% CI low > 0 AND
    cumulative R > 0. The full forward rule is forward_success (Amendment 2
    adds the null-p95 condition)."""
    lo, _ = bootstrap_expectancy_ci(rs)
    return lo > 0.0 and sum(rs) > 0.0


def null_p95_threshold(nets: list[float]) -> float:
    """Amendment 2 condition 2 (pre-specified, stricter reading): with null
    net-R values sorted ascending, threshold = sorted[min(n-1, ceil(0.95*n))]
    (0-based) — the 'higher' order statistic above nearest-rank."""
    s = sorted(nets)
    return s[min(len(s) - 1, math.ceil(0.95 * len(s)))]


def forward_success(rs: list[float], null_p95: float) -> bool:
    """Pre-committed EDGE FOUND rule (Amendment 2), ALL THREE jointly:
    (i) cumulative R > 0 (guards a negative null p95 in a bad regime);
    (ii) 95% CI on expectancy excludes 0 from above;
    (iii) cumulative R STRICTLY exceeds the null p95."""
    return success_criterion(rs) and sum(rs) > null_p95


def max_drawdown_path(rs: list[float]) -> float:
    equity = peak = dd = 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
    return dd


def cumulative_min(rs: list[float]) -> float:
    equity, low = 0.0, 0.0
    for r in rs:
        equity += r
        low = min(low, equity)
    return low


def ruin_probability(rs: list[float], budget_r: float, horizon_trades: int,
                     resamples: int = 10_000, block: int = 10, seed: int = 7,
                     demean: bool = False,
                     peak_relative: bool = False) -> float:
    """P(path touches budget_r within horizon_trades) by moving-block
    resampling. Kill semantics default to the spec's cumulative-R rule;
    peak_relative=True reports the (stricter) peak-to-trough variant."""
    if not rs:
        return float("nan")
    base = rs
    if demean:
        mu = sum(rs) / len(rs)
        base = [r - mu for r in rs]
    rng = random.Random(seed)
    hits = 0
    for _ in range(resamples):
        path = moving_block_resample(rng, base, block, target_len=horizon_trades)
        equity = peak = 0.0
        for r in path[:horizon_trades]:
            equity += r
            peak = max(peak, equity)
            ref = equity - peak if peak_relative else equity
            if ref <= budget_r:
                hits += 1
                break
    return hits / resamples


def time_under_water_days(stream: list[tuple[int, float]]) -> float:
    """Longest stretch (days) from an equity peak to its recovery trade; an
    open stretch at the end counts up to the last trade's timestamp."""
    if not stream:
        return 0.0
    equity = peak = 0.0
    peak_ts = stream[0][0]
    worst_ms = 0
    under = False
    for ts, r in stream:
        equity += r
        if equity >= peak:
            if under:  # the recovering trade closes the underwater stretch
                worst_ms = max(worst_ms, ts - peak_ts)
                under = False
            peak = equity
            peak_ts = ts
        else:
            under = True
            worst_ms = max(worst_ms, ts - peak_ts)
    return worst_ms / _DAY_MS


def trades_per_year(stream: list[tuple[int, float]]) -> float:
    if len(stream) < 2:
        return 0.0
    span_days = (stream[-1][0] - stream[0][0]) / _DAY_MS
    if span_days <= 0:
        return 0.0
    return len(stream) / span_days * 365.0


def required_n(mu: float, sigma: float, alpha: float = 0.05,
               power: float = 0.80) -> int:
    """Trades for a two-sided (1-alpha) CI to exclude 0 with `power` when the
    true edge is mu. power=0.5 collapses to N = ceil((z*sigma/mu)^2)."""
    nd = NormalDist()
    z_a = nd.inv_cdf(1 - alpha / 2)
    z_b = nd.inv_cdf(power)
    return math.ceil(((z_a + z_b) * sigma / mu) ** 2)


def stream_sigma(rs: list[float]) -> float:
    return pstdev(rs) if len(rs) > 1 else 0.0
