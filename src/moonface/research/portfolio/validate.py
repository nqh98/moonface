"""Walk-forward ECON_BAR + sealed validation for a portfolio return series."""
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.kernel.econ import ECON_BAR, evaluate_econ


def econ_walk_forward_portfolio(returns: list[float], test_bars: int,
                                step_bars: int) -> dict:
    """Roll windows over the portfolio return series; summarize_r per window;
    evaluate against ECON_BAR. Mirrors edge_search.econ_walk_forward on a series."""
    n = len(returns)
    windows: list[list[float]] = []
    start = 0
    while start + test_bars <= n:
        windows.append(returns[start:start + test_bars])
        start += step_bars
    if not windows:
        return {"n_windows": 0, "passed": False, "reasons": ["no_windows"],
                "metrics": {}}
    summaries = [summarize_r(w) for w in windows]
    aggregated = summarize_r(returns)
    verdict = evaluate_econ(summaries, aggregated, ECON_BAR)
    return {"n_windows": len(windows), "passed": verdict.passed,
            "reasons": list(verdict.reasons), "metrics": verdict.metrics}


def summarize_portfolio_sealed(returns_sealed: list[float]) -> dict:
    """Compact summary of the sealed holdout segment."""
    from moonface.research.portfolio.evaluate import summarize_portfolio
    return summarize_portfolio(returns_sealed)


def validate_portfolio(returns_train_oos: list[float], returns_sealed: list[float],
                       test_bars: int, step_bars: int) -> dict:
    """ECON_BAR walk-forward on train+oos; sealed last-20% opened here only."""
    econ = econ_walk_forward_portfolio(returns_train_oos, test_bars, step_bars)
    sealed = summarize_portfolio_sealed(returns_sealed)
    return {"econ": econ, "sealed": sealed,
            "passed": econ["passed"] and sealed["net_return"] > 0}
