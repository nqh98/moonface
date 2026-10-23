"""v3 engine config: frozen defaults, disabled-by-default, stable hash."""
from pathlib import Path

from moonface.models.engine.v3.config_v3 import (
    ENGINE_V3_VERSION,
    EngineConfigV3,
    load_engine_config_v3,
    engine_hash_v3,
)


def test_defaults_are_disabled_and_versioned():
    cfg = EngineConfigV3()
    assert cfg.enabled is False
    assert ENGINE_V3_VERSION == "v3"
    assert cfg.asset == {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"}
    assert cfg.lookback_bars == 6000
    assert cfg.adx_period == 14
    assert cfg.breakout_n == 20
    assert cfg.q_floor_reversion == 0.30
    assert cfg.base_fraction == 0.005 and cfg.max_fraction == 0.02


def test_hash_is_stable_and_ignores_enabled():
    a = EngineConfigV3()
    b = EngineConfigV3(enabled=True)
    assert engine_hash_v3(a) == engine_hash_v3(b)
    assert len(engine_hash_v3(a)) == 64


def test_hash_changes_when_a_frozen_param_changes():
    base = EngineConfigV3()
    moved = EngineConfigV3(adx_trend=30.0)
    assert engine_hash_v3(base) != engine_hash_v3(moved)


def test_load_engine_config_v3_falls_back_on_invalid_input(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"max_fraction":"bad","unknown":123}')
    assert load_engine_config_v3(path) == EngineConfigV3()


def test_load_engine_config_v3_returns_fresh_defaults(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("not json")
    cfg1 = load_engine_config_v3(path)
    cfg1.asset["exchange"] = "mutated"
    cfg2 = load_engine_config_v3(path)
    assert cfg2.asset["exchange"] == "binance"


def test_load_engine_config_v3_merges_partial_asset(tmp_path: Path):
    path = tmp_path / "asset.json"
    path.write_text('{"asset":{"symbol":"ETH/USDT:USDT"}}')
    cfg = load_engine_config_v3(path)
    assert cfg.asset == {
        "exchange": "binance",
        "symbol": "ETH/USDT:USDT",
        "timeframe": "1h",
    }


def test_engine_config_schema_matches_plan():
    assert set(EngineConfigV3.__dataclass_fields__) == {
        "asset",
        "lookback_bars",
        "adx_period",
        "adx_trend",
        "ema_fast",
        "ema_slow",
        "atr_period",
        "vol_baseline",
        "vol_quiet_ratio",
        "vol_high_ratio",
        "vol_extreme_ratio",
        "breakout_n",
        "roc_n",
        "ext_scale",
        "roc_scale",
        "pullback_ema",
        "pullback_tol",
        "adx_scale",
        "band_period",
        "band_k",
        "rsi_period",
        "stretch_scale",
        "q_floor_breakout",
        "q_floor_pullback",
        "q_floor_reversion",
        "enabled",
        "base_fraction",
        "max_fraction",
    }
