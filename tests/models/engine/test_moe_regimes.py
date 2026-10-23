from moonface.models.engine.moe.regimes import MoeRegime, TRADEABLE, coarsen
from moonface.models.engine.v3.regime import DirState, Regime, VolState


def test_extreme_maps_to_flat():
    r = Regime(DirState.TRENDING_UP, VolState.EXTREME)
    assert coarsen(r) is MoeRegime.FLAT


def test_trending_normal_maps_to_trend():
    r = Regime(DirState.TRENDING_DOWN, VolState.NORMAL)
    assert coarsen(r) is MoeRegime.TREND


def test_ranging_quiet_maps_to_chop():
    r = Regime(DirState.RANGING, VolState.QUIET)
    assert coarsen(r) is MoeRegime.CHOP


def test_ranging_high_maps_to_stress():
    r = Regime(DirState.RANGING, VolState.HIGH)
    assert coarsen(r) is MoeRegime.STRESS


def test_flat_not_tradeable():
    assert MoeRegime.FLAT not in TRADEABLE
    assert set(TRADEABLE) == {MoeRegime.TREND, MoeRegime.CHOP, MoeRegime.STRESS}
