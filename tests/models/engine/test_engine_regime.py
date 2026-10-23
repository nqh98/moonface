# tests/test_engine_regime.py
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.regime import Regime, classify_regime

H4 = 4 * 3_600_000


def _series(closes, vol=0.0):
    # vol adds symmetric high/low spread to drive vol_ratio when desired
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(i * H4, c, c + vol, c - vol, c, 1.0))
    return out


def test_uptrend_detected():
    cfg = EngineConfig(regime_ma_fast=3, regime_ma_slow=5, vol_window=4)
    candles = _series([float(x) for x in range(1, 40)])  # steadily rising
    r = classify_regime(candles, cfg)
    assert r.trend == 1


def test_downtrend_detected():
    cfg = EngineConfig(regime_ma_fast=3, regime_ma_slow=5, vol_window=4)
    candles = _series([float(x) for x in range(40, 1, -1)])
    assert classify_regime(candles, cfg).trend == -1


def test_flat_is_no_trend():
    cfg = EngineConfig(regime_ma_fast=3, regime_ma_slow=5, vol_window=4)
    candles = _series([10.0] * 40)
    assert classify_regime(candles, cfg).trend == 0


def test_insufficient_history_is_no_trend():
    cfg = EngineConfig(regime_ma_slow=50)
    assert classify_regime(_series([1.0, 2.0, 3.0]), cfg).trend == 0


def test_vol_state_buckets():
    cfg = EngineConfig(regime_ma_fast=3, regime_ma_slow=5, vol_window=4,
                       high_vol_ratio=1.5, extreme_vol_ratio=2.5)
    r = classify_regime(_series([10.0] * 40), cfg)
    assert r.vol_state in {"normal", "high", "extreme"}
    assert isinstance(r, Regime)
