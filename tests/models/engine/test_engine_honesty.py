# tests/test_engine_honesty.py
"""Pure honesty-metric helpers used by the live-faithful engine verdict report.
A trade is (exit_ts_ms, r, atr_frac, fraction)."""
from moonface.models.engine.honesty import (cost_stress, outlier_dependence,
                                            recency_breakdown)

H = 3_600_000
YR = 365 * 24 * H


def _trade(ts, r, atr_frac=0.02, fraction=0.01):
    return (ts, r, atr_frac, fraction)


def test_cost_stress_subtracts_extra_cost_per_trade():
    # one trade, r=+1.0, atr_frac=0.02, base cost 0.001 already netted.
    # 2x cost subtracts an extra (2-1)*0.001/0.02 = 0.05 R.
    trades = [_trade(0, 1.0, atr_frac=0.02)]
    cs = cost_stress(trades, base=0.001)
    assert cs["net_r_1x"] == 1.0
    assert cs["net_r_2x"] == round(1.0 - 0.05, 4)
    assert cs["net_r_3x"] == round(1.0 - 0.10, 4)


def test_outlier_dependence_flags_top_trades():
    rs = [10.0, 1.0, 1.0, 1.0, -2.0]   # net 11, one big winner
    o = outlier_dependence(rs)
    assert o["net_r"] == 11.0
    assert o["best_trade_r"] == 10.0
    assert o["net_r_ex_best1"] == 1.0          # 11 - 10
    assert o["net_r_ex_best3"] == -1.0         # 11 - (10+1+1)


def test_recency_breakdown_buckets_by_exit_time():
    # span 0..100*YR; mid at 50*YR; last_365d cut at 99*YR.
    last = 100 * YR
    trades = [_trade(10 * YR, 5.0),     # first half
              _trade(60 * YR, -3.0),    # second half, not last year
              _trade(995 * H * 100, 0.0)]  # placeholder ignore
    trades = [_trade(10 * YR, 5.0), _trade(60 * YR, -3.0),
              _trade(100 * YR - 1, 2.0)]   # within last 365d
    rb = recency_breakdown(trades, first_ts=0, last_ts=last)
    assert rb["full"]["trades"] == 3
    assert rb["first_half"]["trades"] == 1
    assert rb["first_half"]["net_r"] == 5.0
    assert rb["second_half"]["trades"] == 2
    assert rb["last_365d"]["trades"] == 1
    assert rb["last_365d"]["net_r"] == 2.0


def test_recency_breakdown_empty_is_safe():
    rb = recency_breakdown([], first_ts=0, last_ts=YR)
    assert rb["full"]["trades"] == 0
    assert rb["full"]["net_r"] == 0.0
