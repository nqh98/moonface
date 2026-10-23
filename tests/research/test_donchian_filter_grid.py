from moonface.research.donchian_filter import grid


def test_frozen_grid_constants():
    assert grid.ADX_PERIOD == 14
    assert grid.THRESHOLDS == (18, 20, 25)
    assert grid.N_TRIALS == 3

    assert grid.TRAIN_START == 1577836800000
    assert grid.TRAIN_END == 1698796800000
    assert grid.VALIDATE_END == 1740787200000
    assert grid.SEALED_END == 1782300000000

    assert grid.YEAR_BARS == 2190
    assert grid.QUARTER_BARS == 547
    assert grid.TREND_CAPTURE_FRAC == 0.90
    assert grid.ACTIVITY_FRAC == 0.50
    assert grid.HOLDOUT_MIN_TRADES == 10
    assert grid.NEUTRAL_TOL_R == 5.0
    assert grid.SYMBOL == "BTCUSDT"
    assert grid.TF == "4h"


def test_deployed_base_config():
    from tools.engine.swing_donchian import _BASE

    deployed = grid.deployed_base()

    assert deployed.entry_n == 40
    assert deployed.trail_n == 20
    assert deployed.exit_mode == _BASE.exit_mode
