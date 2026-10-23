import inspect

from moonface.core.exits import EXIT_REGISTRY
from moonface.research import ladder, xsection
from moonface.research.drift_basket import basket, diagnostics, gate, legs


def test_exit_registry_membership_unchanged():
    assert set(EXIT_REGISTRY) == {
        "horizon_hold", "atr_trail", "horizon_wide_stop",
        "breakeven_horizon", "fixed_bracket"}


def test_frozen_params_match_spec():
    p = basket.BasketParams()
    assert (p.donchian_n, p.hold_bars, p.top_n) == (20, 12, 30)
    assert p.vol_target_annual == 0.20
    assert (p.min_history_days, p.vol_days, p.vol_window, p.beta_window) == (180, 30, 30, 30)


def test_drift_basket_does_not_shadow_shared_helpers():
    # the lane reuses build_universe / ladder by import; it must not redefine them
    assert not hasattr(basket, "build_universe")
    assert not hasattr(gate, "DRAWDOWN_BUDGET") or gate.DRAWDOWN_BUDGET is ladder.DRAWDOWN_BUDGET
    assert "build_universe" in dir(xsection)


def test_gate_uses_program_drawdown_budget():
    src = inspect.getsource(gate)
    assert "DRAWDOWN_BUDGET" in src           # reused, not a private constant
    assert "-0.30" not in src and "-0.3" not in src  # no hardcoded budget


def test_modules_are_pure_no_network_imports():
    for mod in (legs, basket, diagnostics, gate):
        src = inspect.getsource(mod)
        assert "urllib" not in src and "requests" not in src
        assert "universe_data" not in src     # IO lives only in the CLI
