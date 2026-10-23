"""Size-only scoring: monotone quality->fraction, zero below the floor."""
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.sizing import q_floor_for, size_from_quality

CFG = EngineConfigV3()


def test_below_floor_is_zero():
    assert size_from_quality("BREAKOUT", 0.19, CFG) == 0.0
    assert size_from_quality("REVERSION", 0.29, CFG) == 0.0


def test_monotone_non_decreasing_in_quality():
    prev = -1.0
    for q in [x / 100 for x in range(20, 101)]:
        f = size_from_quality("BREAKOUT", q, CFG)
        assert f >= prev
        prev = f


def test_caps_at_max_fraction():
    assert size_from_quality("BREAKOUT", 1.0, CFG) == CFG.max_fraction


def test_floor_lookup_per_mechanism():
    assert q_floor_for("BREAKOUT", CFG) == CFG.q_floor_breakout
    assert q_floor_for("PULLBACK", CFG) == CFG.q_floor_pullback
    assert q_floor_for("REVERSION", CFG) == CFG.q_floor_reversion
