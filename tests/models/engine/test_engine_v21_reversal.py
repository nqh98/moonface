from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.confluence import Decision, VETO_LONG_ONLY, VETO_NO_CT
from moonface.models.engine.engine import _reversal_direction, evaluate_engine

H = 3_600_000


def _cfg(**kw):
    base = dict(enabled=True, atr_period=10, regime_ma_fast=10,
                regime_ma_slow=20, vol_window=8)
    base.update(kw)
    return EngineConfig(**base)


def _flat_series(n, price=100.0):
    return [Candle(i * H, price, price, price, price, 1.0) for i in range(n)]


def _open_long(version: str, price: float = 100.0) -> list[dict]:
    return [{
        "strategy_version": version,
        "status": "engine",
        "action": "OPEN",
        "decision": "LONG",
        "entry_price": price,
        "stop": price - 4.0,
        "extreme": price,
        "atr_at_entry": 2.0,
        "fraction": 0.005,
        "bars_held": 0,
        "profile": "WT",
    }]


def _decision(**kw) -> Decision:
    base = dict(action="WAIT", direction=0, archetype=None, policy=None,
                score=70, max_attainable=100, breadth=4, tier=None, veto=None,
                shadow_score=None, modules=(), detail="test",
                shadow_direction=None)
    base.update(kw)
    return Decision(**base)


def test_reversal_direction_uses_only_the_long_only_shadow():
    assert _reversal_direction(_decision(action="SETUP", veto=VETO_LONG_ONLY,
                                         shadow_direction=-1)) == -1
    assert _reversal_direction(_decision(action="SETUP", direction=1)) == 1
    assert _reversal_direction(_decision(action="SETUP", direction=-1)) == -1
    assert _reversal_direction(_decision(veto=VETO_LONG_ONLY,
                                         shadow_direction=-1)) == -1
    assert _reversal_direction(_decision(veto=VETO_NO_CT,
                                         shadow_direction=-1)) == 0
    assert _reversal_direction(_decision(veto="macro BEAR vetoes TREND long",
                                         shadow_direction=-1)) == 0


def test_evaluate_engine_closes_open_long_only_on_long_only_shadow(monkeypatch):
    cfg = _cfg()
    version = engine_hash(cfg)
    candles = _flat_series(40)
    entries = _open_long(version)
    monkeypatch.setattr(
        "moonface.models.engine.engine.decide",
        lambda *args, **kwargs: _decision(veto=VETO_LONG_ONLY,
                                          shadow_direction=-1),
    )

    res = evaluate_engine(cfg, DataBundle(candles=candles), entries, now_ms=0)
    assert res.action == "EXIT"
    assert "reversal" in res.signal.reason.lower()


def test_evaluate_engine_ignores_ct_and_macro_shadow_exits(monkeypatch):
    cfg = _cfg()
    version = engine_hash(cfg)
    candles = _flat_series(40)
    entries = _open_long(version)

    for decision in (
        _decision(veto=VETO_NO_CT, shadow_direction=-1),
        _decision(veto="macro BULL vetoes TREND short", shadow_direction=-1),
    ):
        monkeypatch.setattr(
            "moonface.models.engine.engine.decide",
            lambda *args, _decision=decision, **kwargs: _decision,
        )
        res = evaluate_engine(cfg, DataBundle(candles=candles), entries,
                              now_ms=0)
        assert res.action == "HOLD"
        assert "reversal" not in res.signal.reason.lower()
