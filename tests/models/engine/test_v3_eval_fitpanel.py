"""Fit panel: floor-free overlapping trigger stream for train-window fitting."""

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import fit_panel

from tests.helpers_v3 import uptrend

CFG3 = EngineConfigV3()
CFG22 = EngineConfig()


def test_fit_panel_produces_trades_with_metadata():
    panel = fit_panel(uptrend(600), CFG3, CFG22, lookback=200)
    assert len(panel) > 0
    for tr in panel:
        assert tr.mechanism in ("BREAKOUT", "PULLBACK", "REVERSION")
        assert 0.0 <= tr.quality <= 1.0
        assert "/" in tr.cell


def test_fit_panel_is_overlapping_not_one_position():
    panel = fit_panel(uptrend(600), CFG3, CFG22, lookback=200)
    entries = [tr.entry_index for tr in panel]
    assert len(entries) == len(set(entries))
    assert any(
        panel[i + 1].entry_index <= panel[i].exit_index
        for i in range(len(panel) - 1)
    )
