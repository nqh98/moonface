from __future__ import annotations

from moonface.core.metrics import (Summary, _kurtosis, _sharpe, _skew,
                                          deflated_sharpe, summarize_r)
from moonface.kernel.econ import ECON_BAR, EconVerdict, evaluate_econ
from moonface.research.exogenous.backtest import daily_returns, episode_trades
from moonface.research.exogenous.conditioning import state_positions
from moonface.research.exogenous.grid import PRECOMMITTED_STATES


def _positions(decision_ts, series_by_id):
    return state_positions(decision_ts, series_by_id, states=PRECOMMITTED_STATES)


def walk_forward_summaries(closes, decision_ts, series_by_id, n_windows: int = 4,
                           vol_window: int = 20, cost: float = 0.001):
    rets = daily_returns(closes)
    pos = _positions(decision_ts, series_by_id)
    n = min(len(pos), len(rets))
    pos, rets = pos[:n], rets[:n]
    step = max(1, n // n_windows)
    windows: list[Summary] = []
    for w in range(n_windows):
        lo = w * step
        hi = n if w == n_windows - 1 else (w + 1) * step
        windows.append(summarize_r(episode_trades(pos[lo:hi], rets[lo:hi], vol_window, cost)))
    aggregated = summarize_r(episode_trades(pos, rets, vol_window, cost))
    return windows, aggregated


def dsr_of_trades(trades, n_trials: int) -> float:
    if len(trades) < 2:
        return 0.0
    return deflated_sharpe(_sharpe(trades), len(trades), _skew(trades),
                           _kurtosis(trades), [], n_trials)


def econ_verdict(closes, decision_ts, series_by_id, n_windows: int = 4) -> EconVerdict:
    windows, aggregated = walk_forward_summaries(closes, decision_ts, series_by_id, n_windows)
    return evaluate_econ(windows, aggregated, ECON_BAR)
