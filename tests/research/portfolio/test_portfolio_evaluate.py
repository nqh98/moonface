"""Tests for portfolio equity metrics (Task 7)."""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.portfolio.evaluate import (
    equity_metrics, summarize_portfolio,
)


def _candles(prices, tf_ms=3_600_000):
    return [Candle(timestamp_ms=t * tf_ms, open=p, high=p * 1.01,
                   low=p * 0.99, close=p, volume=1.0) for t, p in enumerate(prices)]


# --- equity_metrics ---

def test_equity_metrics_zeros_on_empty():
    m = equity_metrics([])
    assert m["net_return"] == 0.0 and m["max_drawdown"] == 0.0
    assert m["mar"] == 0.0


def test_equity_metrics_positive_trend():
    m = equity_metrics([0.01, 0.01, 0.01, 0.01])
    assert m["net_return"] > 0
    assert m["max_drawdown"] == 0.0
    assert m["mar"] == float("inf")


def test_equity_metrics_drawdown_sign():
    m = equity_metrics([0.05, -0.10, 0.02])
    assert m["max_drawdown"] < 0.0


def test_equity_metrics_mar_negative_when_loss_with_drawdown():
    m = equity_metrics([-0.01, -0.01])
    # net_return < 0, max_drawdown < 0 → MAR = net/|dd| = -1.0
    assert m["mar"] == -1.0


def test_equity_metrics_n_and_sharpe():
    m = equity_metrics([0.02, -0.01, 0.03])
    assert m["n"] == 3
    assert "sharpe" in m


# --- summarize_portfolio ---

def test_summarize_portfolio_has_all_fields():
    s = summarize_portfolio([0.01, -0.02, 0.03, 0.01, -0.005])
    for k in ("n", "net_return", "expectancy_r", "profit_factor",
              "mar", "max_dd_r", "sharpe"):
        assert k in s


def test_summarize_portfolio_empty():
    s = summarize_portfolio([])
    assert s["n"] == 0
    assert s["net_return"] == 0.0
    assert s["expectancy_r"] == 0.0
    assert s["profit_factor"] == 0.0


def test_summarize_portfolio_pf_inf_when_no_losses():
    s = summarize_portfolio([0.01, 0.02, 0.03])
    assert s["profit_factor"] == float("inf")


def test_summarize_portfolio_pf_value():
    s = summarize_portfolio([0.02, -0.01, 0.03, -0.02])
    wins = sum(r for r in [0.02, -0.01, 0.03, -0.02] if r > 0)
    losses = abs(sum(r for r in [0.02, -0.01, 0.03, -0.02] if r < 0))
    assert s["profit_factor"] == wins / losses


def test_summarize_portfolio_expectancy_r():
    s = summarize_portfolio([0.01, -0.01])
    assert s["expectancy_r"] == 0.0


# --- portfolio_returns delegation ---

def test_portfolio_returns_delegates_to_position_returns():
    """portfolio_returns must produce identical output to streams.position_returns."""
    from moonface.research.portfolio.evaluate import portfolio_returns
    from moonface.research.portfolio.streams import position_returns, asset_bar_r

    prices = [100.0, 101.0, 102.0, 101.0, 100.0, 102.0, 104.0]
    candles = _candles(prices)
    abr = asset_bar_r(candles, period=14)
    positions = [0.0, 1.0, 1.0, -1.0, -1.0, 0.0, 0.0]

    direct = position_returns(positions, abr, candles)
    delegated = portfolio_returns(positions, abr, candles)

    assert len(direct) == len(delegated)
    for d, dd in zip(direct, delegated):
        assert abs(d - dd) < 1e-12, f"mismatch: {d} vs {dd}"
