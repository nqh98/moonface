"""Portfolio per-bar returns and equity metrics (common-currency scale)."""
from __future__ import annotations

from moonface.core.metrics import _sharpe


def portfolio_returns(positions: list[float], asset_bar_r: list[float],
                      grid_candles, atr_period: int = 14) -> list[float]:
    """Per-bar portfolio P&L. Delegates to streams.position_returns so portfolio
    and component returns share one cost model (turnover-based, round-trip-correct)."""
    from moonface.research.portfolio.streams import position_returns
    return position_returns(positions, asset_bar_r, grid_candles, atr_period)


def equity_metrics(returns: list[float]) -> dict:
    """Compounded equity-curve metrics. max_drawdown is a fraction (<=0)."""
    if not returns:
        return {"net_return": 0.0, "max_drawdown": 0.0, "mar": 0.0,
                "sharpe": 0.0, "n": 0}
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= (1.0 + r)
        peak = max(peak, equity)
        dd = (equity / peak) - 1.0
        max_dd = min(max_dd, dd)
    net_return = equity - 1.0
    if max_dd < 0:
        mar = net_return / abs(max_dd)
    elif net_return > 0:
        mar = float("inf")
    else:
        mar = 0.0
    return {"net_return": net_return, "max_drawdown": max_dd, "mar": mar,
            "sharpe": _sharpe(returns), "n": len(returns)}


def summarize_portfolio(returns: list[float]) -> dict:
    """Compact portfolio summary for leaderboard / gate consumption."""
    m = equity_metrics(returns)
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    gross_loss = abs(sum(losses))
    if losses and gross_loss != 0:
        pf = sum(wins) / gross_loss
    elif wins:
        pf = float("inf")
    else:
        pf = 0.0
    return {
        "n": m["n"],
        "net_return": m["net_return"],
        "expectancy_r": (sum(returns) / len(returns)) if returns else 0.0,
        "profit_factor": pf,
        "mar": m["mar"],
        "max_dd_r": m["max_drawdown"],
        "sharpe": m["sharpe"],
    }
