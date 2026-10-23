from moonface.research.regime_selector import grid as G


def test_frozen_bases():
    assert G.TREND_FAMILY == "atr_channel_break"
    assert G.TREND_PARAMS == {"atr_period": 14, "k": 1.5}
    assert G.TREND_EXIT == "atr_trail"
    assert G.TREND_EXIT_PARAMS == {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}
    assert G.TREND_H == 48
    assert G.MR_FAMILY == "reversion_in_range"
    assert G.MR_PARAMS == {"period": 14, "low": 25, "high": 75}
    assert G.MR_EXIT == "fixed_bracket"
    assert G.MR_EXIT_PARAMS == {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}
    assert G.MR_H == 24


def test_four_cells_and_trials():
    assert G.REGIME_IDS == ("R1", "R3")
    assert G.RISKOFF_ACTIONS == ("switch", "wait")
    ids = [c.cell_id for c in G.CELLS]
    assert ids == ["R1-switch", "R1-wait", "R3-switch", "R3-wait"]
    assert G.N_TRIALS == 4
    for c in G.CELLS:
        assert c.regime_id in G.REGIME_IDS
        assert c.riskoff_action in G.RISKOFF_ACTIONS


def test_windows_and_controls():
    assert G.TRAIN_START == 1577836800000
    assert G.TRAIN_END == 1698796800000 == G.VALIDATE_START
    assert G.VALIDATE_END == 1740787200000 == G.SEALED_START
    assert G.SEALED_END == 1782300000000
    assert G.CONTROL_KINDS == ("always_trend", "always_mr", "swap")
    assert G.BTC_SYMBOL == "BTCUSDT" and G.BTC_TF == "4h"
    assert G.FRED_SERIES == ("SP500", "VIXCLS", "DTWEXBGS")
