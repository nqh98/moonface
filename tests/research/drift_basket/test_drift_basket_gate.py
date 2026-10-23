from moonface.research.drift_basket.gate import gate_stages


def test_strong_series_can_pass_all_stages():
    # steady positive daily returns -> no drawdown, high Sharpe, MAR=inf
    returns = [0.005 + (i % 5) * 0.005 for i in range(250)]
    fence = int(len(returns) * 0.8)
    res = gate_stages(returns, fence)
    assert res["stage1_pass"] is True
    assert res["stage2_pass"] is True       # drawdown 0 >= -0.30
    assert res["stage3_pass"] is True       # dsr ~1.0 with n_trials=1
    assert res["stage4_pass"] is True
    assert res["verdict"] == "paper_candidate"


def test_drawdown_breach_fails_stage2_and_verdict():
    # a holdout segment that breaches the -30% budget
    research = [0.01] * 100 + [-0.02] * 60   # the back half digs a deep hole
    returns = research + [0.01] * 40
    fence = len(research)
    res = gate_stages(returns, fence)
    assert res["stage2_pass"] is False
    assert res["verdict"] == "closed_negative"


def test_negative_screen_fails_stage1():
    returns = [-0.005] * 200
    res = gate_stages(returns, int(len(returns) * 0.8))
    assert res["stage1_pass"] is False
    assert res["verdict"] == "closed_negative"
