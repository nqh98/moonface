"""Tests for portfolio gates (DSR, 3x cost stress, bar battery, ensemble)."""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.portfolio.gates import (
    DSR_FLOOR,
    COST_MULTIPLIER,
    MIN_TRADES,
    DROP_FRAC,
    RECENT_FRAC,
    ensemble_gate,
    portfolio_battery,
    portfolio_cost_stress,
    portfolio_dsr,
)


def _candles(prices, tf_ms=3_600_000):
    return [Candle(timestamp_ms=t * tf_ms, open=p, high=p * 1.01,
                   low=p * 0.99, close=p, volume=1.0) for t, p in enumerate(prices)]


# --- Frozen constants ---

def test_frozen_constants():
    assert DSR_FLOOR == 0.95
    assert COST_MULTIPLIER == 3.0
    assert MIN_TRADES == 30
    assert DROP_FRAC == 0.05
    assert RECENT_FRAC == 0.2


# --- portfolio_dsr ---

def test_portfolio_dsr_floor_and_keys():
    res = portfolio_dsr([0.01] * 200, trial_srs=[0.5, 0.6, 0.4], n_trials=8)
    assert set(res) >= {"sharpe", "dsr", "passed"}
    assert res["dsr"] >= 0.0
    assert DSR_FLOOR == 0.95


def test_portfolio_dsr_passed_true_when_high_sharpe():
    """Varied positive returns with low n_trials → high DSR → passed."""
    # Constant returns have zero variance → sharpe=0; use varied positives.
    import random
    rng = random.Random(42)
    returns = [0.01 + rng.gauss(0, 0.005) for _ in range(200)]
    res = portfolio_dsr(returns, trial_srs=[0.0, 0.1], n_trials=2)
    assert res["sharpe"] > 0
    assert res["passed"] is True


def test_portfolio_dsr_passed_false_when_zero_returns():
    res = portfolio_dsr([0.0] * 200, trial_srs=[0.5, 0.6], n_trials=8)
    assert res["passed"] is False


# --- portfolio_cost_stress ---

def test_cost_stress_multiplier_frozen_and_runs():
    assert COST_MULTIPLIER == 3.0
    res = portfolio_cost_stress([0.01] * 60, [1.0] * 60, [0.005] * 60,
                                grid_candles=None)
    assert "passed" in res  # grid_candles=None -> flat multiplier*COST_FRACTION per flip
    assert "expectancy_r" in res
    assert "profit_factor" in res


def test_cost_stress_with_grid_candles():
    prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0,
              108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0]
    candles = _candles(prices)
    positions = [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0]
    bar_r = [0.0] + [0.5] * 15
    res = portfolio_cost_stress(bar_r, positions, [0.0] + [0.005] * 15,
                                grid_candles=candles)
    assert "passed" in res


def test_cost_stress_no_flips_no_cost():
    """When positions never change, stressed returns == position * bar_r."""
    res = portfolio_cost_stress(
        [0.01, 0.01, 0.01],
        [0.0, 0.0, 0.0],  # never flips
        [0.005, 0.005, 0.005],
        grid_candles=None,
    )
    # all-zero positions → expectancy should be 0
    assert res["expectancy_r"] == 0.0


def test_cost_stress_custom_multiplier():
    res = portfolio_cost_stress(
        [0.01] * 10,
        [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        [0.005] * 10,
        grid_candles=None,
        multiplier=1.0,
    )
    assert "passed" in res


# --- portfolio_battery ---

def test_battery_min_trades_frozen():
    assert MIN_TRADES == 30


def test_battery_has_six_checks():
    positions = [0.0] * 200
    bar_r = [0.001] * 200
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    assert set(res) >= {"checks", "passed"}
    assert set(res["checks"]) == {
        "trade_count", "outlier", "cost_stress_3x", "recent",
        "regime", "no_lookahead",
    }


def test_battery_trade_count():
    """Many flips should pass trade_count; no flips should fail."""
    # 60 flips → passes
    positions_60 = ([0.0] + [float(i % 2) for i in range(1, 61)])
    bar_r_60 = [0.001] * 61
    res = portfolio_battery(bar_r_60, positions_60, bar_r_60, grid_candles=None)
    assert res["checks"]["trade_count"]["passed"] is True
    assert res["checks"]["trade_count"]["n"] == 60

    # 10 flips → fails
    positions_10 = ([0.0] + [float(i % 2) for i in range(1, 11)])
    bar_r_10 = [0.001] * 11
    res2 = portfolio_battery(bar_r_10, positions_10, bar_r_10, grid_candles=None)
    assert res2["checks"]["trade_count"]["passed"] is False


def test_battery_outlier_check():
    """Trimmed returns positive → passes; all-negative → fails."""
    # All positive → trimmed also positive
    positions = [0.0] * 200
    bar_r = [0.001] * 200
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    assert res["checks"]["outlier"]["passed"] is True

    # All negative → trimmed also negative
    neg_bar_r = [-0.001] * 200
    res2 = portfolio_battery(neg_bar_r, positions, neg_bar_r, grid_candles=None)
    assert res2["checks"]["outlier"]["passed"] is False


def test_battery_recent_check():
    """Recent slice positive → passes; negative → fails."""
    positions = [0.0] * 100
    bar_r = [0.001] * 100
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    assert res["checks"]["recent"]["passed"] is True
    assert res["checks"]["recent"]["n"] == 20  # RECENT_FRAC=0.2 of 100


def test_battery_regime_check():
    """Both halves positive → passes. Both halves negative → fails."""
    positions = [0.0] * 100
    bar_r = [0.001] * 100
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    assert res["checks"]["regime"]["passed"] is True

    # Both halves negative → major < 0 → fails
    neg_bar_r = [-0.001] * 100
    res2 = portfolio_battery(neg_bar_r, positions, neg_bar_r, grid_candles=None)
    assert res2["checks"]["regime"]["passed"] is False


def test_battery_no_lookahead_always_true():
    positions = [0.0] * 50
    bar_r = [0.001] * 50
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    assert res["checks"]["no_lookahead"]["passed"] is True


def test_battery_passed_is_and_of_all_six():
    """passed must be True only when ALL 6 sub-checks pass."""
    # All positive, many flips, no stress damage → all pass
    positions = [float(i % 2) for i in range(200)]  # 199 flips
    bar_r = [0.01] * 200
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    # With high returns, cost stress should still be ok
    if res["checks"]["cost_stress_3x"]["passed"]:
        assert res["passed"] is True

    # Zero returns, zero flips → trade_count fails → battery fails
    positions_0 = [0.0] * 50
    bar_r_0 = [0.001] * 50
    res2 = portfolio_battery(bar_r_0, positions_0, bar_r_0, grid_candles=None)
    assert res2["checks"]["trade_count"]["passed"] is False
    assert res2["passed"] is False  # AND → False


def test_battery_passed_is_false_when_cost_stress_fails():
    """When cost_stress_3x fails, battery must fail even if other checks pass."""
    # Create returns that are positive at base cost but negative at 3x cost
    # Use tiny returns that get eaten by 3x cost on flip
    positions = [0.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0,
                 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0,
                 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0,
                 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0]
    bar_r = [0.0001] * 34  # tiny returns
    res = portfolio_battery(bar_r, positions, bar_r, grid_candles=None)
    # The cost stress will be punishing with many flips on tiny returns
    # The battery's passed must reflect cost_stress_3x["passed"]
    assert res["passed"] == res["checks"]["cost_stress_3x"]["passed"]


# --- ensemble_gate ---

def test_ensemble_gate_requires_both_conditions():
    # portfolio MAR must beat best comp AND DD <= 80% of best comp DD
    good = ensemble_gate({"mar": 1.0, "max_dd_r": -0.10},
                         {"mar": 0.5, "max_dd_r": -0.20})
    assert good["passed"] is True
    bad_mar = ensemble_gate({"mar": 0.3, "max_dd_r": -0.10},
                            {"mar": 0.5, "max_dd_r": -0.20})
    assert bad_mar["passed"] is False  # MAR did not beat best
    bad_dd = ensemble_gate({"mar": 1.0, "max_dd_r": -0.19},
                           {"mar": 0.5, "max_dd_r": -0.20})
    assert bad_dd["passed"] is False  # DD > 80% of best (-0.16)


def test_ensemble_gate_dd_boundary():
    """DD exactly at 80% of best → passes (<= not <)."""
    # 80% of -0.20 = -0.16
    res = ensemble_gate({"mar": 1.0, "max_dd_r": -0.16},
                        {"mar": 0.5, "max_dd_r": -0.20})
    assert res["passed"] is True


def test_ensemble_gate_dd_direction():
    """max_dd_r is negative (drawdown). Less negative = smaller drawdown = better.
    80% threshold: portfolio |dd| <= 0.8 * best |dd|."""
    # portfolio dd=-0.05, best dd=-0.10 → |0.05| <= 0.8*|0.10|=0.08 → pass
    res = ensemble_gate({"mar": 1.0, "max_dd_r": -0.05},
                        {"mar": 0.5, "max_dd_r": -0.10})
    assert res["passed"] is True


def test_ensemble_gate_output_keys():
    res = ensemble_gate({"mar": 1.0, "max_dd_r": -0.10},
                        {"mar": 0.5, "max_dd_r": -0.20})
    assert set(res) >= {"passed", "mar", "best_mar", "max_dd_r", "best_max_dd_r"}
