# tests/test_engine_config.py
import pytest

from moonface.models.engine import config as engine_config
from moonface.models.engine import confluence, discipline, macro, position
from moonface.models.engine.config import (EngineConfig, engine_hash,
                                           load_engine_config)
from moonface.models.engine.modules import revert_book, trend_book

V2_FROZEN_HASH = "10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf"
V22_FROZEN_HASH = "b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5"


def test_absent_file_is_disabled_default():
    cfg = load_engine_config("/nonexistent/engine.json")
    assert isinstance(cfg, EngineConfig)
    assert cfg.enabled is False
    assert cfg.asset["timeframe"] == "1h"


def test_invalid_json_is_disabled_default(tmp_path):
    p = tmp_path / "engine.json"
    p.write_text("{not json")
    assert load_engine_config(p).enabled is False


def test_recognised_keys_override(tmp_path):
    p = tmp_path / "engine.json"
    p.write_text('{"enabled": true, "k_stop": 3.0, "bogus": 9}')
    cfg = load_engine_config(p)
    assert cfg.enabled is True
    assert cfg.k_stop == 3.0
    assert not hasattr(cfg, "bogus")


def test_hash_excludes_enabled(tmp_path):
    on = EngineConfig(enabled=True)
    off = EngineConfig(enabled=False)
    assert engine_hash(on) == engine_hash(off)
    assert engine_hash(EngineConfig(k_stop=2.0)) != engine_hash(EngineConfig(k_stop=3.0))


def test_hash_folds_in_engine_version(monkeypatch):
    # the engine version is folded into the payload, so a version bump changes
    # the hash — v1 journal entries become invisible to v2 reconstruct.
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(engine_config, "ENGINE_VERSION", "different")
    assert engine_hash(cfg) != baseline


def test_engine_version_is_v22():
    assert engine_config.ENGINE_VERSION == "2.2"


def test_hash_matches_v22_identity():
    assert engine_hash(EngineConfig()) != V2_FROZEN_HASH
    assert engine_hash(EngineConfig()) == V22_FROZEN_HASH


def test_hash_changes_when_confluence_excluded_modules_change(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(confluence, "EXCLUDED_MODULES", ())
    assert engine_hash(cfg) != baseline


def test_hash_is_deterministic():
    cfg = EngineConfig(k_stop=2.5, max_fraction=0.03)
    assert engine_hash(cfg) == engine_hash(cfg)


def test_hash_changes_when_trend_breakout_constant_changes(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(trend_book, "W_BREAKOUT", 21)
    assert engine_hash(cfg) != baseline


def test_hash_changes_when_confluence_gate_changes(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    gate = dict(confluence.GATE)
    gate[("BULL", "TREND", "LONG")] = "REJECT"
    monkeypatch.setattr(confluence, "GATE", gate)
    assert engine_hash(cfg) != baseline


def test_hash_changes_when_discipline_tier_profile_fraction_changes(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    tier_profile_fraction = dict(discipline._TIER_PROFILE_FRACTION)
    tier_profile_fraction[("A", "WT")] = 0.011
    monkeypatch.setattr(discipline, "_TIER_PROFILE_FRACTION",
                        tier_profile_fraction)
    assert engine_hash(cfg) != baseline


def test_hash_changes_when_macro_constants_change(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(macro, "MACRO_MA_WEEKS", macro.MACRO_MA_WEEKS + 1)
    assert engine_hash(cfg) != baseline


def test_hash_changes_when_position_constants_change(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(position, "CT_STOP_ATR", position.CT_STOP_ATR + 0.1)
    assert engine_hash(cfg) != baseline


def test_hash_changes_when_revert_book_constants_change(monkeypatch):
    cfg = EngineConfig()
    baseline = engine_hash(cfg)
    monkeypatch.setattr(revert_book, "W_SWEEP", revert_book.W_SWEEP + 1)
    assert engine_hash(cfg) != baseline


def test_hash_rejects_unlisted_frozen_constant(monkeypatch):
    cfg = EngineConfig()
    monkeypatch.setattr(trend_book, "W_FUTURE", 1, raising=False)
    with pytest.raises(RuntimeError, match="frozen constant drift"):
        engine_hash(cfg)
