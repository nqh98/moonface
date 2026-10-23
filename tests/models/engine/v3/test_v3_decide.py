"""decide_v3 orchestration + the spec-2 core invariant (score never trades)."""
import moonface.models.engine.v3.decide as decide_mod
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.decide import DecisionV3, decide_v3
from moonface.models.engine.v3.mechanisms.base import MechanismSignal
from moonface.models.engine.v3.regime import DirState, Regime, VolState

from tests.helpers_v3 import uptrend

CFG = EngineConfigV3()


class _Spy:
    def __init__(self, name, signal):
        self.name = name
        self.signal = signal
        self.calls = 0

    def evaluate(self, ctx, regime):
        self.calls += 1
        return self.signal


def _force_regime(monkeypatch, regime):
    monkeypatch.setattr(decide_mod, "classify_regime", lambda candles, cfg: regime)


def test_extreme_vol_waits_before_any_selection(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.EXTREME))
    called = {"select": False}
    monkeypatch.setattr(decide_mod, "select_mechanism",
                        lambda r: called.__setitem__("select", True))
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT" and called["select"] is False


def test_empty_cell_waits(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.RANGING, VolState.HIGH))
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT" and d.mechanism is None


def test_nontriggering_bar_never_enters_even_with_max_quality(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.NORMAL))
    spy = _Spy("BREAKOUT", MechanismSignal(0, 1.0, "no trigger"))
    monkeypatch.setattr(decide_mod, "MECHANISMS", {"BREAKOUT": spy})
    monkeypatch.setattr(decide_mod, "select_mechanism", lambda r: "BREAKOUT")
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT"


def test_exactly_one_mechanism_is_consulted(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.NORMAL))
    chosen = _Spy("BREAKOUT", MechanismSignal(1, 0.9, "hit"))
    other = _Spy("REVERSION", MechanismSignal(-1, 0.9, "should not run"))
    monkeypatch.setattr(decide_mod, "MECHANISMS",
                        {"BREAKOUT": chosen, "REVERSION": other})
    monkeypatch.setattr(decide_mod, "select_mechanism", lambda r: "BREAKOUT")
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "ENTER" and d.direction == 1
    assert chosen.calls == 1 and other.calls == 0
    assert d.risk_fraction > 0.0


def test_degenerate_quality_veto_waits(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.NORMAL))
    spy = _Spy("BREAKOUT", MechanismSignal(1, 0.05, "below floor"))
    monkeypatch.setattr(decide_mod, "MECHANISMS", {"BREAKOUT": spy})
    monkeypatch.setattr(decide_mod, "select_mechanism", lambda r: "BREAKOUT")
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT" and d.risk_fraction == 0.0


def test_decision_is_frozen_and_serializable_shape():
    d = decide_v3(uptrend(140), 139, CFG)
    assert isinstance(d, DecisionV3)
    assert d.action in ("ENTER", "WAIT")
    assert d.risk_fraction >= 0.0
