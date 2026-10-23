"""Fitted one-position stream applies the fitted floor + pruned matrix."""

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import (
    fitted_cfg,
    v3_stream,
)
from moonface.models.engine.v3.matrix import REGIME_MECHANISM

from tests.helpers_v3 import uptrend

CFG3 = EngineConfigV3()
CFG22 = EngineConfig()


def test_fitted_cfg_replaces_floors():
    cfg = fitted_cfg(CFG3, {"BREAKOUT": 0.5, "PULLBACK": 0.6, "REVERSION": 0.7})
    assert cfg.q_floor_breakout == 0.5 and cfg.q_floor_reversion == 0.7


def test_stream_is_one_position_and_non_overlapping():
    pairs = v3_stream(uptrend(600), CFG3, dict(REGIME_MECHANISM), CFG22,
                      lookback=200)
    prev_exit = -1
    for trade, atr_frac in pairs:
        assert trade.entry_index > prev_exit
        assert atr_frac > 0.0
        prev_exit = trade.exit_index


def test_pruned_matrix_suppresses_all_entries():
    empty = {k: None for k in REGIME_MECHANISM}
    assert v3_stream(uptrend(600), CFG3, empty, CFG22, lookback=200) == []


def test_high_floor_suppresses_all_entries():
    veto = fitted_cfg(CFG3, {"BREAKOUT": 1.0, "PULLBACK": 1.0,
                             "REVERSION": 1.0})
    assert v3_stream(uptrend(600), veto, dict(REGIME_MECHANISM), CFG22,
                     lookback=200) == []
