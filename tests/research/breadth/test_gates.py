from __future__ import annotations

from moonface.research.breadth.gates import (
    cost_multiple,
    cost_stress,
    practical_pass,
)


def test_cost_stress_reduces_expectancy() -> None:
    recs = [{"net_r": 1.0, "atr_frac": 0.01} for _ in range(5)]
    base = cost_stress(recs, 0.0)
    worse = cost_stress(recs, 0.0005)
    assert worse["expectancy_r"] < base["expectancy_r"]
    assert cost_multiple(recs, 3.0)["expectancy_r"] < cost_multiple(recs, 2.0)["expectancy_r"]


def test_practical_pass_requires_all_gates() -> None:
    good = {
        "profit_factor": 1.3,
        "expectancy_r": 0.1,
        "max_drawdown_r": -5.0,
        "trade_count": 40,
    }
    bad_dd = {**good, "max_drawdown_r": -45.0}
    assert practical_pass(good) is True
    assert practical_pass(bad_dd) is False
