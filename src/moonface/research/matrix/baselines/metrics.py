from __future__ import annotations

import math
from dataclasses import dataclass

from moonface.research.matrix.baselines.strategies import BaselineTrade

MS_PER_YEAR = 31_557_600_000
MS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class BaselineMetrics:
    trade_count: int
    ev_per_trade: float
    net_return: float
    cagr: float
    max_drawdown: float
    max_dd_duration_days: float
    mar: float
    es95: float


def _equity_walk(returns: list[float]) -> tuple[float, float]:
    equity = peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= 1.0 + r
        if equity <= 0.0:
            return -1.0, -1.0
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    return equity - 1.0, max_dd


def _dd_duration_days(trades: list[BaselineTrade]) -> float:
    equity = peak = 1.0
    peak_ts = trades[0].entry_ts_ms
    worst = 0.0
    for t in trades:
        equity *= 1.0 + t.net_return
        if equity >= peak:
            peak = equity
            peak_ts = t.exit_ts_ms
        else:
            worst = max(worst, t.exit_ts_ms - peak_ts)
    return worst / MS_PER_DAY


def _es95(returns: list[float]) -> float:
    k = max(1, math.ceil(0.05 * len(returns)))
    worst = sorted(returns)[:k]
    return sum(worst) / len(worst)


def baseline_metrics(trades: list[BaselineTrade]) -> BaselineMetrics:
    if not trades:
        return BaselineMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    rets = [t.net_return for t in trades]
    net, max_dd = _equity_walk(rets)
    years = (trades[-1].exit_ts_ms - trades[0].entry_ts_ms) / MS_PER_YEAR
    equity = 1.0 + net
    cagr = equity ** (1.0 / years) - 1.0 if years > 0 and equity > 0 else 0.0
    if max_dd == 0.0:
        mar = math.inf if cagr > 0 else 0.0
    else:
        mar = cagr / abs(max_dd)
    return BaselineMetrics(
        trade_count=len(trades),
        ev_per_trade=round(sum(rets) / len(rets), 8),
        net_return=round(net, 6),
        cagr=cagr if math.isinf(cagr) else round(cagr, 6),
        max_drawdown=round(max_dd, 6),
        max_dd_duration_days=round(_dd_duration_days(trades), 2),
        mar=mar if math.isinf(mar) else round(mar, 4),
        es95=round(_es95(rets), 8),
    )
