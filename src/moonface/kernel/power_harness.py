from __future__ import annotations

import random

from moonface.core.metrics import COST_FRACTION, summarize_r
from moonface.kernel.bootstrap import circular_block_resample, iid_resample_randrange

FAMILY_ALPHA: float = 0.05
PF_FLOOR: float = 1.15
MAX_DD_R: float = 30.0
MIN_TRADES: int = 30


def bonferroni_level(k: int) -> float:
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    return FAMILY_ALPHA / k


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _resample_mean_iid(rng: random.Random, data: list[float]) -> float:
    return _mean(iid_resample_randrange(rng, data))


def _resample_mean_block(
    rng: random.Random,
    data: list[float],
    block_len: int,
) -> float:
    """Kept defined (not inlined) -- research.liq_twap.screen imports this
    function directly."""
    return _mean(circular_block_resample(rng, data, block_len))


def pooled_metrics(records: list[dict]) -> dict:
    s = summarize_r([r["net_r"] for r in records])
    return {
        "trade_count": s.trade_count,
        "total_r": s.total_r,
        "expectancy_r": s.expectancy_r,
        "profit_factor": s.profit_factor,
        "max_drawdown_r": s.max_drawdown_r,
    }


def cost_multiple(records: list[dict], mult: float) -> bool:
    stressed = [
        r["net_r"] - (mult - 1.0) * COST_FRACTION / r["atr_frac"]
        if r["atr_frac"] > 0
        else r["net_r"]
        for r in records
    ]
    s = summarize_r(stressed)
    return s.expectancy_r > 0 and s.profit_factor > 1.0


def _practical(metrics: dict) -> bool:
    return (
        metrics["profit_factor"] >= PF_FLOOR
        and metrics["expectancy_r"] > 0
        and abs(metrics["max_drawdown_r"]) <= MAX_DD_R
        and metrics["trade_count"] >= MIN_TRADES
    )


def bootstrap_expectancy(
    net_rs: list[float],
    n_resamples: int = 100_000,
    seed: int = 20260627,
    block: bool = False,
    block_len: int = 1,
) -> tuple[list[float], float]:
    if n_resamples <= 0:
        raise ValueError(f"n_resamples must be positive, got {n_resamples}")
    if block_len <= 0:
        raise ValueError(f"block_len must be positive, got {block_len}")
    if not net_rs:
        # Keep the current plan-compatible bootstrap sentinel:
        # no data means no resamples and a neutral upper-tail probability.
        return [], 1.0

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        if block and block_len > 1:
            means.append(_resample_mean_block(rng, net_rs, block_len))
        else:
            means.append(_resample_mean_iid(rng, net_rs))

    means.sort()
    p_le_zero = sum(1 for mean in means if mean <= 0.0) / n_resamples
    return means, p_le_zero


def one_sided_lower(sorted_means: list[float], alpha: float) -> float:
    """Return the lower one-sided percentile from an already-sorted sample.

    Args:
        sorted_means: Bootstrap means in ascending order.
        alpha: Percentile fraction in the inclusive range [0, 1].
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be between 0 and 1, got {alpha}")
    if not sorted_means:
        return 0.0
    idx = int(alpha * len(sorted_means))
    idx = min(max(idx, 0), len(sorted_means) - 1)
    return sorted_means[idx]


def judge_signal(
    validate: dict,
    sealed: dict,
    pooled_records: list[dict],
    k: int,
    *,
    n_resamples: int = 100_000,
    seed: int = 20260627,
    block: bool = False,
    block_len: int = 1,
) -> dict:
    pooled = pooled_metrics(pooled_records)
    alpha = bonferroni_level(k)
    means, p_le_zero = bootstrap_expectancy(
        [r["net_r"] for r in pooled_records],
        n_resamples=n_resamples,
        seed=seed,
        block=block,
        block_len=block_len,
    )
    boot_lo = one_sided_lower(means, alpha)
    same_sign = (validate["expectancy_r"] > 0) == (sealed["expectancy_r"] > 0)
    practical = _practical(pooled)
    cost = cost_multiple(pooled_records, 2.0) and cost_multiple(pooled_records, 3.0)
    significant = p_le_zero < alpha
    if same_sign and practical and cost and significant:
        verdict = "paper_candidate"
    elif same_sign and pooled["expectancy_r"] > 0 and not significant:
        verdict = "forward_candidate"
    else:
        verdict = "negative"
    return {
        "pooled": pooled,
        "boot_lo": boot_lo,
        "p_le_zero": p_le_zero,
        "same_sign": same_sign,
        "practical": practical,
        "cost": cost,
        "significant": significant,
        "verdict": verdict,
    }
