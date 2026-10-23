from __future__ import annotations

from moonface.research.exogenous.forward import forward_report

WEEK_MS = 7 * 24 * 3600 * 1000


def test_inconclusive_when_too_few_trades():
    r = forward_report([0.1, 0.2], t0_ms=0, now_ms=20 * WEEK_MS)
    assert r["outcome"] == "INCONCLUSIVE"


def test_early_dd_kill():
    # a drawdown beyond budget triggers DOWNGRADE_DD even with 1 trade
    r = forward_report([-0.5], t0_ms=0, now_ms=1 * WEEK_MS)
    assert r["outcome"] == "DOWNGRADE_DD"
    assert r["gate"]["drawdown_within_p95"] is False


def test_reaffirm_full_gate():
    trades = [0.1] * 25
    r = forward_report(trades, t0_ms=0, now_ms=13 * WEEK_MS)
    assert r["outcome"] == "REAFFIRM"
    assert r["gate"]["passed"] is True
