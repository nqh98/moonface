# tests/test_pathsig_evaluate.py
from moonface.core.metrics import equity_summary_from_returns
from moonface.research.pathsig.evaluate import evaluate_strategy, realized_r
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Decision


def test_equity_summary_from_returns_matches_manual_walk():
    s = equity_summary_from_returns([0.1, -0.05, 0.2])
    # 1.1 * 0.95 * 1.2 = 1.254 -> net 0.254
    assert s.net_return == round(1.1 * 0.95 * 1.2 - 1.0, 6)
    assert s.trade_count == 3


def test_realized_r_directions():
    lbl = PathLabel(ret_r=1.5, mae_r=-0.8, mfe_r=2.0)
    assert realized_r(Decision("LONG", 0.02), lbl) == 1.5
    assert realized_r(Decision("SHORT", 0.02), lbl) == -1.5
    assert realized_r(Decision("WAIT", 0.0), lbl) is None


def test_evaluate_reports_both_frames():
    labels = [PathLabel(ret_r=1.0, mae_r=-0.5, mfe_r=1.2) for _ in range(40)]
    decisions = [Decision("LONG", 0.01) for _ in range(40)]
    atr_fracs = [0.02] * 40
    fundings = [0.0] * 40
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=0.0, slippage_bps=0.0,
                            n_trials=10, trial_srs=[], drawdown_cap_r=15.0)
    assert res["risk_adjusted"]["trade_count"] == 40
    assert "dsr" in res["risk_adjusted"]
    assert "total_r" in res["fixed_cap"]
    assert "max_drawdown_r" in res["fixed_cap"]
    assert isinstance(res["fixed_cap"]["within_cap"], bool)


def test_within_cap_false_when_drawdown_exceeds_cap():
    # a large losing LONG drives the fixed-cap R drawdown past the cap
    labels = [PathLabel(ret_r=-6.0, mae_r=-8.0, mfe_r=0.5)]
    decisions = [Decision("LONG", 0.01)]
    res = evaluate_strategy(decisions, labels, [0.02], [0.0],
                            taker_bps=0.0, slippage_bps=0.0,
                            n_trials=1, trial_srs=[], drawdown_cap_r=5.0)
    assert res["fixed_cap"]["within_cap"] is False
    assert res["fixed_cap"]["max_drawdown_r"] == -6.0


def test_wait_decisions_excluded_from_both_frames():
    labels = [PathLabel(ret_r=1.0, mae_r=-0.5, mfe_r=1.2),
              PathLabel(ret_r=-1.0, mae_r=-0.5, mfe_r=0.5),
              PathLabel(ret_r=1.0, mae_r=-0.5, mfe_r=1.2)]
    decisions = [Decision("LONG", 0.01), Decision("WAIT", 0.0),
                 Decision("LONG", 0.01)]
    res = evaluate_strategy(decisions, labels, [0.02, 0.02, 0.02],
                            [0.0, 0.0, 0.0], taker_bps=0.0, slippage_bps=0.0,
                            n_trials=1, trial_srs=[], drawdown_cap_r=15.0)
    # the WAIT (index 1) is excluded from both frames -> 2 trades each
    assert res["risk_adjusted"]["trade_count"] == 2
    assert res["fixed_cap"]["trade_count"] == 2
    assert res["fixed_cap"]["total_r"] == 2.0  # 1.0 + 1.0 from the two LONGs
