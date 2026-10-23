"""Gate 1: validation with 3x cost, deflated block CI, drawdown, power floor."""

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.evaluate import V3Trade, gate1_validation

CFG22 = EngineConfig()
H = 3_600_000


def _pairs(n, net_r):
    out = []
    for i in range(n):
        tr = V3Trade(
            entry_index=i * 10,
            exit_index=i * 10 + 1,
            entry_ts_ms=i * 10 * H,
            exit_ts_ms=(i * 10 + 1) * H,
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
            entry_index=i * 10,
            exit_index=i * 10 + 1,
            entry_ts_ms=i * 10 * H,
            exit_ts_ms=(i * 10 + 1) * H,
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


def test_below_panel_floor_fails():
    g = gate1_validation(_pairs(50, 0.3), {"max_dd_r": -1.0})
    assert g["passed"] is False


def test_strong_positive_passes():
    g = gate1_validation(_pairs(300, 0.3), {"max_dd_r": -100.0})
    assert g["passed"] is True
    assert g["ci"][0] > 0 and g["net_r_3x"] > 0


def test_worse_drawdown_than_baseline_fails():
    g = gate1_validation(
        _pairs_seq([0.3] * 295 + [-0.05] * 5),
        {"max_dd_r": -0.01},
    )
    assert g["passed"] is False
