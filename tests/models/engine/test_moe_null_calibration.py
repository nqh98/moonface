import random

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.evaluate_moe import build_fit_panel, null_calibration
from moonface.models.engine.moe.experts import default_experts
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import LOOKBACK, SPAN_START_TS_MS, TRAIN_END_TS_MS

import pytest

pytestmark = pytest.mark.slow


DAY_MS = 86_400_000


def _make_candles(n: int, seed: int = 1729) -> list[Candle]:
    rng = random.Random(seed)
    candles: list[Candle] = []
    price = 100.0
    for i in range(n):
        drift = 0.0015 if (i // 80) % 2 == 0 else -0.0012
        noise = rng.uniform(-0.01, 0.01)
        open_ = price
        close = max(1.0, price * (1.0 + drift + noise))
        high = max(open_, close) * (1.0 + rng.uniform(0.0, 0.006))
        low = min(open_, close) * (1.0 - rng.uniform(0.0, 0.006))
        volume = 1000.0 + rng.uniform(-200.0, 200.0)
        candles.append(Candle(SPAN_START_TS_MS + i * DAY_MS, open_, high, low, close, volume))
        price = close
    return candles


def _funding_series(n: int) -> list[float]:
    return [0.004 * (((i // 11) % 3) - 1) for i in range(n)]


def _oi_series(n: int) -> list[float]:
    return [900.0 + (i % 37) * 4.0 + ((i // 45) % 2) * 25.0 for i in range(n)]


def test_gate0_returns_negative_on_nulls():
    candles = _make_candles(3000)
    funding = _funding_series(len(candles))
    oi = _oi_series(len(candles))
    result = null_calibration(
        candles,
        EngineConfigV3(),
        EngineConfig(),
        default_experts(),
        MoeConfig(),
        funding=funding,
        oi=oi,
    )
    assert result["passed_negative"] is True, result
    assert any(run["n"] > 0 for run in result["runs"].values()), result


def test_fit_panel_respects_train_end():
    candles = _make_candles(1600)
    funding = _funding_series(len(candles))
    oi = _oi_series(len(candles))
    experts = default_experts()
    samples, train_series = build_fit_panel(
        candles,
        EngineConfigV3(),
        EngineConfig(),
        experts,
        lookback=LOOKBACK,
        end_ts_ms=TRAIN_END_TS_MS,
        funding=funding,
        oi=oi,
    )
    start = min(LOOKBACK, len(candles))
    expected = sum(1 for i in range(start, len(candles)) if candles[i].timestamp_ms < TRAIN_END_TS_MS)
    for expert in experts:
        assert len(train_series[expert.name]) == expected
    unbounded_samples, _ = build_fit_panel(
        candles,
        EngineConfigV3(),
        EngineConfig(),
        experts,
        lookback=LOOKBACK,
        funding=funding,
        oi=oi,
    )
    assert len(samples) <= len(unbounded_samples)
