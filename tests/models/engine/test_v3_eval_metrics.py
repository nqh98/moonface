"""Metrics + v2.2 baseline reuse the repair replay machinery."""

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.evaluate import (
    V3Trade,
    split_pairs_by_window,
    v3_metrics,
)

CFG22 = EngineConfig()


def _pair(exit_ts, net_r, frac):
    tr = V3Trade(
        entry_index=0,
        exit_index=1,
        entry_ts_ms=0,
        exit_ts_ms=exit_ts,
        direction=1,
        mechanism="BREAKOUT",
        quality=0.5,
        risk_fraction=frac,
        net_r=net_r,
        bars_held=1,
        exit_reason="target",
        cell="X/Y",
    )
    return (tr, 0.02)


def test_v3_metrics_has_replay_keys_plus_size_weight():
    pairs = [_pair(10, 1.0, 0.02), _pair(20, -0.5, 0.005)]
    m = v3_metrics(pairs, CFG22)
    assert set(m) >= {"n", "net_r", "max_dd_r", "cost_stress",
                      "size_weighted_net_r"}
    assert m["n"] == 2
    assert abs(m["net_r"] - 0.5) < 1e-9
    base = CFG22.base_fraction
    expect_w = 1.0 * (0.02 / base) + (-0.5) * (0.005 / base)
    assert abs(m["size_weighted_net_r"] - round(expect_w, 4)) < 1e-3


def test_split_pairs_by_window():
    pairs = [_pair(5, 1.0, 0.02), _pair(150, 1.0, 0.02),
             _pair(400, 1.0, 0.02)]
    got = split_pairs_by_window(pairs, 100, 300)
    assert [p[0].exit_ts_ms for p in got] == [150]
