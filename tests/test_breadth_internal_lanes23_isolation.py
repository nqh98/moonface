import inspect

import moonface.kernel.power_harness as power_harness
from moonface.core.exits import EXIT_REGISTRY
from moonface.research.breadth_internal import evaluate as l1_evaluate
from moonface.research.breadth_internal import grid as l1_grid
from moonface.research.breadth_internal.hf_grid import BLOCK_LEN, hf_specs


def test_exit_registry_membership_unchanged():
    assert set(EXIT_REGISTRY) == {
        "horizon_hold", "atr_trail", "horizon_wide_stop",
        "breakeven_horizon", "fixed_bracket"}


def test_power_harness_no_deflation_machinery():
    src = inspect.getsource(power_harness)
    assert "deflated_sharpe" not in src
    assert "breadth.evaluate" not in src


def test_lane2_grid_is_three_and_distinct_from_lane1():
    hf = hf_specs()
    assert len(hf) == 3
    assert BLOCK_LEN == 8
    l1_keys = {s.key for s in l1_grid.all_specs()}
    hf_keys = {s.key for s in hf}
    assert l1_keys.isdisjoint(hf_keys)  # Lane 2 introduces new signals


def test_lane2_reuses_frozen_exit():
    for s in hf_specs():
        assert s.exit_name == "atr_trail"
        assert dict(s.exit_params) == {
            "k_trail": 2.0, "max_bars": 120, "atr_period": 14}


def test_lane1_evaluate_builders_untouched():
    # Lane 1 still exposes exactly its four builders (Lane 2 added a separate map).
    assert set(l1_evaluate._BUILDERS) == {
        "breadth_thrust", "net_new_highs", "breadth_divergence", "dispersion_regime"}
