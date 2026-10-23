# src/moonface/core/metrics.py
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist, fmean

from moonface.core.exits import EXECUTABLE_EXITS
from moonface.core.risk import risk_unit


MAX_LEVERAGE = 5.0  # cap on implied notional/equity per trade


@dataclass(frozen=True)
class EquitySummary:
    """Geometric (compounding) equity stats for an R stream at fixed fraction f.

    Per-trade return = f_eff * r (leverage-clamped). max_drawdown is the worst
    peak-to-trough equity fraction (<= 0). MAR = net_return / |max_drawdown|;
    +inf when there is no drawdown and net is positive. kurtosis is raw
    (normal -> 3.0)."""

    trade_count: int
    net_return: float
    max_drawdown: float
    mar: float
    sharpe: float
    skew: float
    kurtosis: float


def _equity_walk(returns: list[float]) -> tuple[float, float]:
    """Compound returns into (net_return, max_drawdown). Ruin (equity <= 0)
    clamps to (-1.0, -1.0)."""
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret in returns:
        equity *= 1.0 + ret
        if equity <= 0.0:
            return -1.0, -1.0
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    return equity - 1.0, max_dd


def equity_summary_from_returns(returns: list[float]) -> EquitySummary:
    """EquitySummary for an explicit, already-sized per-trade return stream
    (used by the path-signal evaluator where each trade carries its own
    conviction fraction)."""
    if not returns:
        return EquitySummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0)
    net, max_dd = _equity_walk(returns)
    if max_dd == 0.0:
        mar = math.inf if net > 0 else 0.0
    else:
        mar = net / abs(max_dd)
    return EquitySummary(
        trade_count=len(returns),
        net_return=round(net, 6),
        max_drawdown=round(max_dd, 6),
        mar=mar if math.isinf(mar) else round(mar, 4),
        sharpe=_sharpe(returns),
        skew=_skew(returns),
        kurtosis=_kurtosis(returns),
    )


def equity_summary(trades: list[tuple[float, float]],
                   fraction: float) -> EquitySummary:
    """trades are (R, atr_frac) pairs; atr_frac = 1xATR at entry / entry price.

    Per-trade return = f_eff * r with f_eff = min(fraction,
    MAX_LEVERAGE * atr_frac): risking `fraction` of equity against a stop of
    atr_frac * price implies notional = fraction/atr_frac * equity, so the
    clamp caps implied leverage at MAX_LEVERAGE."""
    if not trades:
        return EquitySummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0)
    returns = [min(fraction, MAX_LEVERAGE * atr_frac) * r
               for r, atr_frac in trades]
    net, max_dd = _equity_walk(returns)
    if max_dd == 0.0:
        mar = math.inf if net > 0 else 0.0
    else:
        mar = net / abs(max_dd)
    return EquitySummary(
        trade_count=len(trades),
        net_return=round(net, 6),
        max_drawdown=round(max_dd, 6),
        mar=mar if math.isinf(mar) else round(mar, 4),
        sharpe=_sharpe(returns),
        skew=_skew(returns),
        kurtosis=_kurtosis(returns),
    )


def _sharpe(returns: list[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = fmean(returns)
    var = sum((x - mean) ** 2 for x in returns) / (n - 1)
    if var <= 0.0:
        return 0.0
    return round(mean / math.sqrt(var), 6)


def _central_moment(returns: list[float], k: int) -> float:
    mean = fmean(returns)
    return sum((x - mean) ** k for x in returns) / len(returns)


def _skew(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    m2 = _central_moment(returns, 2)
    if m2 <= 0.0:
        return 0.0
    return round(_central_moment(returns, 3) / m2**1.5, 6)


def _kurtosis(returns: list[float]) -> float:
    if len(returns) < 2:
        return 3.0
    m2 = _central_moment(returns, 2)
    if m2 <= 0.0:
        return 3.0
    return round(_central_moment(returns, 4) / m2**2, 6)


_EULER_GAMMA = 0.5772156649015329


def expected_max_sharpe(trial_srs: list[float], n_trials: int) -> float:
    """E[max SR] of n_trials zero-skill trials (Bailey & Lopez de Prado).

    Trial-SR variance is estimated from the observed trial SRs; conservative
    default 0.25 when fewer than two are available. n_trials is the FULL
    registered grid size, never the surviving subset."""
    if n_trials < 2:
        return 0.0
    if len(trial_srs) >= 2:
        mean = fmean(trial_srs)
        var = sum((s - mean) ** 2 for s in trial_srs) / (len(trial_srs) - 1)
    else:
        var = 0.25
    nd = NormalDist()
    return math.sqrt(var) * (
        (1.0 - _EULER_GAMMA) * nd.inv_cdf(1.0 - 1.0 / n_trials)
        + _EULER_GAMMA * nd.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    )


def deflated_sharpe(
    sr: float,
    n_obs: int,
    skew: float,
    kurtosis: float,
    trial_srs: list[float],
    n_trials: int,
) -> float:
    """Probability the observed per-trade Sharpe beats the expected max of
    n_trials zero-skill trials, adjusted for return skew/kurtosis."""
    if n_obs < 2:
        return 0.0
    sr0 = expected_max_sharpe(trial_srs, n_trials)
    denom = 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr * sr
    if denom <= 0.0:
        return 0.0
    z = (sr - sr0) * math.sqrt(n_obs - 1.0) / math.sqrt(denom)
    return NormalDist().cdf(z)


@dataclass(frozen=True)
class Summary:
    trade_count: int
    win_rate: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    total_r: float


def summarize_r(rs: list[float]) -> Summary:
    if not rs:
        return Summary(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    total = sum(rs)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")
    peak = 0.0
    equity = 0.0
    max_dd = 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return Summary(
        trade_count=len(rs),
        win_rate=round(len(wins) / len(rs), 4),
        expectancy_r=round(total / len(rs), 4),
        profit_factor=round(profit_factor, 4) if profit_factor != float("inf") else profit_factor,
        max_drawdown_r=round(max_dd, 4),
        total_r=round(total, 4),
    )


COST_FRACTION = 0.001  # round-trip taker fee + slippage, fraction of notional

_EXIT_FNS = {name: fn for name, (fn, _grid) in EXECUTABLE_EXITS.items()}


def single_trade_r(candles, i: int, side: str, exit_name: str,
                   exit_params: dict) -> tuple[float, float] | None:
    """(net R, atr_frac) for one entry — the exact math r_stream applies per
    trade. None when the entry is untradeable or the exit cannot resolve."""
    unit = risk_unit(candles, i, 1.0, exit_params["atr_period"])
    if unit is None:
        return None
    r = _EXIT_FNS[exit_name](i, side, candles, exit_params)
    if r is None:
        return None
    atr_frac = unit / candles[i].close
    return r - COST_FRACTION / atr_frac, atr_frac


def resolve_trade_span(candles, i: int, side: str, exit_name: str,
                       exit_params: dict):
    """(entry_idx, exit_idx, net_r, atr_frac) for one entry, or None.

    Mirrors single_trade_r but also returns the exit bar index via the additive
    _SPAN_FNS resolvers in foundation.exits. net_r is identical to single_trade_r
    so per-bar attribution is consistent with the per-trade R convention.
    """
    from moonface.core.exits import _SPAN_FNS  # local import: avoid cycle
    unit = risk_unit(candles, i, 1.0, exit_params["atr_period"])
    if unit is None:
        return None
    span_fn = _SPAN_FNS.get(exit_name)
    if span_fn is None:
        raise KeyError(f"no span resolver for exit {exit_name!r}")
    span = span_fn(i, side, candles, exit_params)
    if span is None:
        return None
    exit_idx, r = span
    atr_frac = unit / candles[i].close
    return i, exit_idx, r - COST_FRACTION / atr_frac, atr_frac
