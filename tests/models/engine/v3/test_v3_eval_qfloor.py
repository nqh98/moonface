"""q_floor fit: isotonic E[R] on quality; floor at first non-negative bucket."""

from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import fit_q_floors

CFG3 = EngineConfigV3()


def _tr(mech, quality, net_r, i=[0]):
    from moonface.models.engine.v3.evaluate import V3Trade

    i[0] += 1
    return V3Trade(
        entry_index=i[0],
        exit_index=i[0] + 1,
        entry_ts_ms=i[0],
        exit_ts_ms=i[0] + 1,
        direction=1,
        mechanism=mech,
        quality=quality,
        risk_fraction=0.005,
        net_r=net_r,
        bars_held=1,
        exit_reason="target",
        cell="X/Y",
    )


def test_floor_excludes_negative_low_quality_band():
    train = ([_tr("BREAKOUT", 0.30, -0.5) for _ in range(40)]
             + [_tr("BREAKOUT", 0.80, 0.6) for _ in range(40)])
    floors = fit_q_floors(train, CFG3)
    assert floors["BREAKOUT"] > 0.30
    assert floors["BREAKOUT"] <= 0.80


def test_underpowered_mechanism_keeps_default():
    train = [_tr("PULLBACK", 0.5, 0.1) for _ in range(5)]
    floors = fit_q_floors(train, CFG3)
    assert floors["PULLBACK"] == CFG3.q_floor_pullback


def test_all_positive_gives_floor_at_or_below_min_quality():
    train = [_tr("REVERSION", 0.4 + 0.01 * (n % 20), 0.3) for n in range(40)]
    floors = fit_q_floors(train, CFG3)
    assert floors["REVERSION"] <= 0.4
