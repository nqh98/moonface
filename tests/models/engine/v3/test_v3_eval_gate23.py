"""Gate 2 sealed BTC (sign+drawdown) and Gate 3 ETH/SOL transfer."""

from moonface.models.engine.v3.evaluate import (
    V3Trade,
    gate2_sealed,
    gate3_transfer,
)

H = 3_600_000


def _pairs(n, net_r):
    out = []
    for i in range(n):
        tr = V3Trade(
            entry_index=i,
            exit_index=i + 1,
            entry_ts_ms=i * H,
            exit_ts_ms=(i + 1) * H,
            direction=1,
            mechanism="BREAKOUT",
            quality=0.5,
            risk_fraction=0.005,
            net_r=net_r,
            bars_held=1,
            exit_reason="target",
            cell="X/Y",
        )
        out.append((tr, 0.05))
    return out


def _pairs_seq(values):
    out = []
    for i, net_r in enumerate(values):
        tr = V3Trade(
            entry_index=i,
            exit_index=i + 1,
            entry_ts_ms=i * H,
            exit_ts_ms=(i + 1) * H,
            direction=1,
            mechanism="BREAKOUT",
            quality=0.5,
            risk_fraction=0.005,
            net_r=net_r,
            bars_held=1,
            exit_reason="target",
            cell="X/Y",
        )
        out.append((tr, 0.05))
    return out


def test_gate2_positive_sign_and_ok_drawdown_passes():
    g = gate2_sealed(_pairs(40, 0.2), {"max_dd_r": -100.0})
    assert g["passed"] is True


def test_gate2_worse_drawdown_fails():
    g = gate2_sealed(_pairs_seq([0.2] * 35 + [-0.05] * 5), {"max_dd_r": -0.001})
    assert g["passed"] is False


def test_gate3_requires_both_assets_positive_and_powered():
    ok = gate3_transfer(_pairs(30, 0.2), _pairs(30, 0.2))
    assert ok["passed"] is True
    one_neg = gate3_transfer(_pairs(30, 0.2), _pairs(30, -0.2))
    assert one_neg["passed"] is False
    thin = gate3_transfer(_pairs(30, 0.2), _pairs(10, 0.2))
    assert thin["passed"] is False
