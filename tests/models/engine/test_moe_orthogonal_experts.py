from moonface.core.models import Candle
from moonface.models.engine.moe.evaluate_moe import _raw_series
from moonface.models.engine.moe.experts import (
    OI_LOOKBACK,
    ExpertContext,
    default_experts,
    orthogonal_experts,
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


def _ctx(candles, funding=None, oi=None):
    return ExpertContext(
        window=candles,
        index=len(candles) - 1,
        cfg=EngineConfigV3(),
        funding=funding,
        oi=oi,
    )


def test_names():
    assert {e.name for e in orthogonal_experts()} == {"FUNDING", "OI"}
    assert [e.name for e in default_experts()] == [
        "BREAKOUT",
        "PULLBACK",
        "REVERSION",
        "FUNDING",
        "OI",
    ]


def test_funding_fades_the_crowd():
    funding = {e.name: e for e in orthogonal_experts()}["FUNDING"]
    candles = _candles(30)
    n = len(candles)
    pos = funding.signal(_ctx(candles, funding=[0.0] * (n - 1) + [0.02]))
    assert pos.direction == -1 and 0.0 < pos.magnitude <= 1.0
    neg = funding.signal(_ctx(candles, funding=[0.0] * (n - 1) + [-0.02]))
    assert neg.direction == 1
    assert funding.signal(_ctx(candles, funding=None)).direction == 0
    assert funding.signal(_ctx(candles, funding=[0.0] * n)).direction == 0


def test_oi_confirms_momentum():
    oi_expert = {e.name: e for e in orthogonal_experts()}["OI"]
    up = _candles(30, step=1.0)
    n = len(up)
    rising_oi = [100.0 + i for i in range(n)]
    sig = oi_expert.signal(_ctx(up, oi=rising_oi))
    assert sig.direction == 1 and 0.0 < sig.magnitude <= 1.0
    falling_oi = [100.0 + (n - i) for i in range(n)]
    assert oi_expert.signal(_ctx(up, oi=falling_oi)).direction == 0
    assert oi_expert.signal(_ctx(up, oi=None)).direction == 0
    assert oi_expert.signal(_ctx(_candles(10), oi=[1.0] * 10)).direction == 0


def test_oi_causal_uses_only_past():
    oi_expert = {e.name: e for e in orthogonal_experts()}["OI"]
    up = _candles(30)
    oi = [100.0 + i for i in range(len(up))]
    base = oi_expert.signal(_ctx(up, oi=oi))
    assert base.direction == 1


def test_oi_raw_series_uses_full_causal_history_at_lookback_threshold():
    oi_expert = {e.name: e for e in orthogonal_experts()}["OI"]
    candles = _candles(OI_LOOKBACK + 2, step=1.0)
    oi = [100.0 + i for i in range(len(candles))]

    bars, _regimes, series = _raw_series(
        candles,
        EngineConfigV3(),
        [oi_expert],
        lookback=OI_LOOKBACK,
        oi=oi,
    )

    assert bars[0] == OI_LOOKBACK
    assert series["OI"][0] > 0.0
