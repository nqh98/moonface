from moonface.research.regime_overlay.evaluate import (beats_base,
                                                       practical_pass,
                                                       vector_from_rt)

YEAR = 365 * 24 * 3_600_000


def test_vector_basic_metrics_and_trailing_window():
    first, last = 0, 2 * YEAR
    # one old win, one recent win, one recent loss
    rt = [(YEAR // 2, 3.0), (last - 10, 2.0), (last - 5, -1.0)]
    v = vector_from_rt(rt, first, last)
    assert v["trades"] == 3
    assert v["net_r"] == 4.0
    assert v["trailing_365d_net_r"] == 1.0      # 2.0 + (-1.0), old win excluded
    assert v["net_r_ex_best1"] == 1.0           # 4.0 - best(3.0)


def test_practical_pass_flags():
    v = {"net_r": 10.0, "max_drawdown_r": -12.0, "trades": 40,
         "net_r_ex_best1": 4.0,
         "cost_stress": {"net_r_1x": 10.0, "net_r_2x": 6.0, "net_r_3x": 2.0}}
    p = practical_pass(v)
    assert p["net_positive"] and p["drawdown_ok"] and p["enough_trades"]
    assert p["outlier_ok"] and p["cost_2x_ok"] and p["cost_3x_ok"]
    assert p["all_pass"]


def test_practical_pass_fails_on_drawdown_and_outlier():
    v = {"net_r": 1.0, "max_drawdown_r": -45.0, "trades": 40,
         "net_r_ex_best1": -2.0,
         "cost_stress": {"net_r_1x": 1.0, "net_r_2x": -1.0, "net_r_3x": -3.0}}
    p = practical_pass(v)
    assert not p["drawdown_ok"]
    assert not p["outlier_ok"]
    assert not p["cost_2x_ok"]
    assert not p["all_pass"]


def test_beats_base_recent():
    base = {"net_r": 5.0, "max_drawdown_r": -20.0, "trailing_365d_net_r": -10.0}
    cell = {"net_r": 7.0, "max_drawdown_r": -15.0, "trailing_365d_net_r": 2.0}
    b = beats_base(cell, base)
    assert b["delta_net_r"] == 2.0
    assert b["delta_max_dd_r"] == 5.0
    assert b["beats_recent"] is True
