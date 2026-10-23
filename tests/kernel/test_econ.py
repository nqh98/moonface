from moonface.core.metrics import Summary
from moonface.kernel.econ import EconBar, ECON_BAR, evaluate_econ  # noqa: F401


def _agg(total_r, exp, pf, mdd, n=100):
    return Summary(trade_count=n, win_rate=0.5, expectancy_r=exp,
                   profit_factor=pf, max_drawdown_r=mdd, total_r=total_r)


def _window(exp, pf, robust=True):
    # max_dd scaled: robust window has small dd; non-robust has large dd
    mdd = -5.0 if robust else -50.0
    return Summary(trade_count=10, win_rate=0.5, expectancy_r=exp,
                   profit_factor=pf, max_drawdown_r=mdd, total_r=exp * 10)


def test_econ_bar_passes_at_frozen_thresholds():
    # aggregated exactly meets: PF 1.2, exp 0.05, MAR = 30/30 = 1.0 >= 0.5,
    # max_dd 30R == 30% at f=0.01 -> within tol; 6/10 windows robust
    wins = [_window(0.06, 1.1)] * 6 + [_window(0.01, 0.9)] * 4
    v = evaluate_econ(wins, _agg(total_r=30.0, exp=0.05, pf=1.2, mdd=-30.0, n=100))
    assert v.passed is True
    assert "all thresholds met" in " ".join(v.reasons).lower()


def test_econ_bar_fails_on_drawdown_breach():
    wins = [_window(0.06, 1.1)] * 7
    v = evaluate_econ(wins, _agg(total_r=20.0, exp=0.05, pf=1.2, mdd=-60.0, n=100))
    assert v.passed is False
    assert any("drawdown" in r.lower() for r in v.reasons)


def test_econ_bar_fails_on_robust_frac_below_floor():
    # only 3/10 windows robust (< 60%)
    wins = [_window(0.06, 1.1)] * 3 + [_window(0.01, 0.9)] * 7
    v = evaluate_econ(wins, _agg(total_r=30.0, exp=0.05, pf=1.2, mdd=-30.0, n=100))
    assert v.passed is False
    assert any("robust" in r.lower() for r in v.reasons)


def test_econ_bar_frozen_values_match_user_lock():
    assert ECON_BAR.profit_factor == 1.2
    assert ECON_BAR.expectancy_r == 0.05
    assert ECON_BAR.mar_floor == 0.5
    assert ECON_BAR.max_dd_r == 30.0
    assert ECON_BAR.robust_frac == 0.6
