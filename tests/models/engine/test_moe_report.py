import random

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.moe.config_moe import MoeConfig, identity_hash
from moonface.models.engine.moe.evaluate_moe import build_moe_report
from moonface.models.engine.moe.experts import (
    ORTHO_CONSTANTS,
    default_experts,
    mechanism_experts,
)
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import SPAN_START_TS_MS

import pytest

pytestmark = pytest.mark.slow


DAY_MS = 86_400_000
VERDICTS = {
    "GATE0_FAILED_HALT",
    "POWER_BUDGET_REFUSED",
    "CLOSED_NEGATIVE_VALIDATION",
    "CLOSED_NEGATIVE_SEALED_BTC",
    "CLOSED_NEGATIVE_TRANSFER",
    "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
}


def _make_candles(n: int, seed: int = 1729) -> list[Candle]:
    rng = random.Random(seed)
    candles: list[Candle] = []
    price = 100.0
    for i in range(n):
        drift = 0.0012 if (i // 70) % 2 == 0 else -0.0010
        noise = rng.uniform(-0.01, 0.01)
        open_ = price
        close = max(1.0, price * (1.0 + drift + noise))
        high = max(open_, close) * (1.0 + rng.uniform(0.0, 0.007))
        low = min(open_, close) * (1.0 - rng.uniform(0.0, 0.007))
        volume = 1000.0 + rng.uniform(-250.0, 250.0)
        candles.append(Candle(SPAN_START_TS_MS + i * DAY_MS, open_, high, low, close, volume))
        price = close
    return candles


def _make_bundle(n: int, seed: int, *, with_ortho: bool = True) -> DataBundle:
    candles = _make_candles(n, seed=seed)
    if not with_ortho:
        return DataBundle(candles=candles, funding=None, feature=None)
    funding = [0.003 * (((i // 9) % 3) - 1) for i in range(n)]
    oi = [1000.0 + (i % 31) * 5.0 + ((i // 50) % 2) * 20.0 for i in range(n)]
    return DataBundle(candles=candles, funding=funding, feature=oi)


def test_report_has_identity_and_frozen_verdict_set():
    btc = _make_bundle(2500, seed=1)
    eth = _make_bundle(2500, seed=2)
    sol = _make_bundle(2500, seed=3)
    cfg_moe = MoeConfig()
    report = build_moe_report(
        btc,
        eth,
        sol,
        EngineConfigV3(),
        EngineConfig(),
        cfg_moe,
        warmup=400,
        lookback=400,
    )
    expert_names = [expert.name for expert in default_experts()]
    assert report["experts"] == expert_names
    assert report["identity_hash"] == identity_hash(cfg_moe, expert_names, ORTHO_CONSTANTS)
    assert report["ortho_constants"] == ORTHO_CONSTANTS
    assert "gate0" in report and "verdict" in report
    assert report["verdict"] in VERDICTS
    gate1 = report["gate1"]
    if not (
        report["gate0"]["passed_negative"]
        and report["power"]["passed"]
        and gate1 is not None
        and gate1["passed"]
    ):
        assert report["gate2"] is None


def test_ortho_none_bundle_matches_price_only_verdict():
    btc = _make_bundle(2500, seed=7, with_ortho=False)
    eth = _make_bundle(2500, seed=8, with_ortho=False)
    sol = _make_bundle(2500, seed=9, with_ortho=False)
    cfg_v3 = EngineConfigV3()
    cfg_v22 = EngineConfig()
    cfg_moe = MoeConfig()
    ortho_none = build_moe_report(
        btc,
        eth,
        sol,
        cfg_v3,
        cfg_v22,
        cfg_moe,
        warmup=400,
        lookback=400,
    )
    price_only = build_moe_report(
        btc.candles,
        eth.candles,
        sol.candles,
        cfg_v3,
        cfg_v22,
        cfg_moe,
        warmup=400,
        lookback=400,
        experts=mechanism_experts(),
    )
    assert ortho_none["verdict"] == price_only["verdict"]


def test_synthetic_noise_does_not_pass():
    btc = _make_bundle(2500, seed=11)
    report = build_moe_report(
        btc,
        btc,
        btc,
        EngineConfigV3(),
        EngineConfig(),
        MoeConfig(),
        warmup=400,
        lookback=400,
    )
    assert report["verdict"] != "ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
