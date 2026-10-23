from moonface.core.models import Candle
from moonface.models.engine.moe.experts import (
    ExpertContext,
    RawSignal,
    mechanism_experts,
    raw_value,
)
from moonface.models.engine.v3.config_v3 import EngineConfigV3


def _candles(n, start=100.0, step=1.0):
    out, p = [], start
    for i in range(n):
        o = p
        cl = p + step
        out.append(
            Candle(
                1_600_000_000_000 + i * 3_600_000,
                o,
                max(o, cl) + 0.2,
                min(o, cl) - 0.2,
                cl,
                1000.0,
            )
        )
        p = cl
    return out


def test_raw_value_is_signed_magnitude():
    assert raw_value(RawSignal(direction=-1, magnitude=0.4)) == -0.4
    assert raw_value(RawSignal(direction=0, magnitude=0.9)) == 0.0


def test_mechanism_experts_named_and_causal():
    experts = mechanism_experts()
    assert {e.name for e in experts} == {"BREAKOUT", "PULLBACK", "REVERSION"}
    candles = _candles(300)
    ctx = ExpertContext(window=candles, index=len(candles) - 1, cfg=EngineConfigV3())
    for e in experts:
        sig = e.signal(ctx)
        assert sig.direction in (-1, 0, 1)
        assert 0.0 <= sig.magnitude <= 1.0
