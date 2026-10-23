# src/moonface/research/universe_donchian_wf.py
"""Rolling walk-forward for universe_donchian (spec §4, stage 3.5).

The construction is frozen (no param selection), so TRAIN_DAYS is only the
warm-up offset before the first test window. The portfolio daily-return series
is precomputed and point-in-time causal, so each contiguous test slice is a
valid OOS window. Pools test-window daily returns, then checks dominance vs the
static-basket control."""
from __future__ import annotations

from moonface.core.metrics import equity_summary_from_returns
from moonface.research.universe_donchian import dominates

TRAIN_DAYS = 365          # ~1yr warm-up offset
TEST_DAYS = 182           # ~6mo test window
STEP_DAYS = TEST_DAYS     # non-overlapping


def walk_forward(t_returns: list[float], c_returns: list[float],
                 train_days: int = TRAIN_DAYS, test_days: int = TEST_DAYS,
                 step_days: int = STEP_DAYS) -> dict:
    n = min(len(t_returns), len(c_returns))
    t_pool: list[float] = []
    c_pool: list[float] = []
    folds = 0
    start = train_days
    while start + test_days <= n:
        t_pool.extend(t_returns[start:start + test_days])
        c_pool.extend(c_returns[start:start + test_days])
        folds += 1
        start += step_days
    t = equity_summary_from_returns(t_pool)
    c = equity_summary_from_returns(c_pool)
    return {
        "folds": folds,
        "aggregate_treatment_mar": t.mar,
        "aggregate_treatment_sharpe": t.sharpe,
        "aggregate_control_mar": c.mar,
        "aggregate_trades": t.trade_count,
        "dominance": dominates(t.mar, t.sharpe, c.mar, c.sharpe),
    }


def stage35_of(wf: dict) -> bool:
    return (wf["folds"] >= 1 and wf["aggregate_treatment_mar"] > 0.0
            and wf["dominance"])
