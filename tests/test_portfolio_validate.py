"""Tests for portfolio walk-forward + sealed validation (Task 9)."""
from __future__ import annotations

from moonface.kernel.econ import ECON_BAR
from moonface.research.portfolio.validate import (
    econ_walk_forward_portfolio,
    validate_portfolio,
    summarize_portfolio_sealed,
)


# --- econ_walk_forward_portfolio ---

def test_walk_forward_returns_metrics_shape():
    returns = [0.001] * 400
    res = econ_walk_forward_portfolio(returns, test_bars=100, step_bars=50)
    assert set(res) >= {"n_windows", "passed", "reasons", "metrics"}
    for k in ("expectancy_r", "profit_factor", "mar", "max_dd_r", "robust_frac"):
        assert k in res["metrics"]
    assert ECON_BAR.profit_factor == 1.2


def test_walk_forward_empty_returns():
    res = econ_walk_forward_portfolio([], test_bars=100, step_bars=50)
    assert res["n_windows"] == 0
    assert res["passed"] is False
    assert "no_windows" in res["reasons"]


def test_walk_forward_too_short_for_one_window():
    res = econ_walk_forward_portfolio([0.01] * 50, test_bars=100, step_bars=50)
    assert res["n_windows"] == 0
    assert res["passed"] is False


def test_walk_forward_single_window():
    returns = [0.01] * 100
    res = econ_walk_forward_portfolio(returns, test_bars=100, step_bars=50)
    assert res["n_windows"] == 1
    assert isinstance(res["metrics"]["expectancy_r"], float)


def test_walk_forward_consistent_returns_pass():
    """Returns with expectancy >= 0.05 and drawdown should pass econ bar."""
    # ECON_BAR requires exp>=0.05, PF>=1.2, MAR>=0.5, dd<=30R, robust>=0.60.
    # 400 bars of 0.1 -> aggregated exp=0.1, total_r=40.0.
    # Per-window (100 bars): total_r=10, max_dd=0 -> MAR=0.0 (< 0.5).
    # So use a mix: 0.2 on 80% of bars, -0.1 on 20% -> exp=0.14, PF>1.
    # With DD: sequence that has a drawdown to give finite MAR.
    import random
    rng = random.Random(42)
    returns = []
    for _ in range(400):
        returns.append(0.1 if rng.random() < 0.8 else -0.05)
    # Add a dip early to create drawdown
    returns[10:20] = [-0.1] * 10
    res = econ_walk_forward_portfolio(returns, test_bars=100, step_bars=50)
    assert res["n_windows"] == 7  # (400-100)//50 + 1
    assert res["passed"] is True
    assert "all thresholds met" in res["reasons"]


def test_walk_forward_negative_returns_fail():
    """Uniform negative returns should fail econ bar."""
    returns = [-0.01] * 400
    res = econ_walk_forward_portfolio(returns, test_bars=100, step_bars=50)
    assert res["passed"] is False
    assert len(res["reasons"]) > 0


def test_walk_forward_n_windows_count():
    """Verify exact window count: start=0,1,2,3 while start+test_bars <= n."""
    # 250 bars, test_bars=100, step_bars=50 -> starts 0,50,100,150 -> 4 windows
    returns = [0.001] * 250
    res = econ_walk_forward_portfolio(returns, test_bars=100, step_bars=50)
    assert res["n_windows"] == 4


# --- summarize_portfolio_sealed ---

def test_summarize_portfolio_sealed_delegates():
    """Must delegate to evaluate.summarize_portfolio and return dict."""
    sealed = summarize_portfolio_sealed([0.01, -0.02, 0.03])
    assert isinstance(sealed, dict)
    assert "net_return" in sealed
    assert "expectancy_r" in sealed
    assert "profit_factor" in sealed


def test_summarize_portfolio_sealed_empty():
    sealed = summarize_portfolio_sealed([])
    assert sealed["n"] == 0
    assert sealed["net_return"] == 0.0


# --- validate_portfolio ---

def test_validate_portfolio_structure():
    """validate_portfolio must return dict with econ + sealed + passed."""
    train = [0.01] * 400
    sealed = [0.01] * 100
    res = validate_portfolio(train, sealed, test_bars=100, step_bars=50)
    assert "econ" in res
    assert "sealed" in res
    assert "passed" in res


def test_validate_portfolio_passes_when_both_pass():
    """Returns with positive expectancy and sealed positive should pass."""
    import random
    rng = random.Random(42)
    train = []
    for _ in range(400):
        train.append(0.1 if rng.random() < 0.8 else -0.05)
    train[10:20] = [-0.1] * 10
    sealed = [0.05] * 100
    res = validate_portfolio(train, sealed, test_bars=100, step_bars=50)
    assert res["passed"] is True


def test_validate_portfolio_fails_when_sealed_negative():
    """Sealed negative return should fail even if econ passes."""
    train = [0.01] * 400
    sealed = [-0.01] * 100
    res = validate_portfolio(train, sealed, test_bars=100, step_bars=50)
    assert res["passed"] is False


def test_validate_portfolio_fails_when_econ_fails():
    """Negative train returns should fail econ even with positive sealed."""
    train = [-0.01] * 400
    sealed = [0.01] * 100
    res = validate_portfolio(train, sealed, test_bars=100, step_bars=50)
    assert res["passed"] is False
