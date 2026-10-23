import inspect

import moonface.kernel.power_harness as power_harness
from moonface.core.exits import EXIT_REGISTRY
from moonface.research.breadth_internal import grid


def test_exit_registry_membership_unchanged() -> None:
    assert set(EXIT_REGISTRY) == {
        "horizon_hold",
        "atr_trail",
        "horizon_wide_stop",
        "breakeven_horizon",
        "fixed_bracket",
    }


def test_power_harness_does_not_touch_breadth_or_deflated_sharpe() -> None:
    src = inspect.getsource(power_harness)
    assert "deflated_sharpe" not in src
    assert "breadth.evaluate" not in src


def test_grid_returns_four_specs() -> None:
    assert len(grid.all_specs()) == 4
