"""Stdlib indicator helpers used by the regime classifier and mechanisms."""
from moonface.models.engine.v3.indicators import (
    adx,
    donchian_high,
    donchian_low,
    ema,
    roc,
    rsi,
    sma,
    stdev,
    vol_ratio,
)

from tests.helpers_v3 import c, flat_range, uptrend


def test_ema_tracks_toward_latest():
    assert abs(ema([10.0] * 20, 10) - 10.0) < 1e-9
    assert ema([0.0] * 10 + [10.0] * 10, 5) > 5.0


def test_roc_signs_with_direction():
    assert roc([100.0, 101.0, 102.0, 110.0], 3) > 0
    assert roc([110.0, 105.0, 100.0], 2) < 0
    assert roc([100.0], 5) == 0.0


def test_sma_and_stdev():
    assert sma([1.0, 2.0, 3.0, 4.0], 4) == 2.5
    assert abs(stdev([2.0, 2.0, 2.0], 3)) < 1e-9
    assert stdev([1.0, 3.0], 2) > 0


def test_donchian_uses_prior_bars_only():
    up = uptrend(30)
    assert up[-1].close > donchian_high(up, 20)
    assert donchian_low(up, 20) < up[-1].close
    assert donchian_high(up, 0) == 0.0
    assert donchian_low(up, -1) == 0.0
    single = uptrend(1)
    assert donchian_high(single, 20) == single[-1].high
    assert donchian_low(single, 20) == single[-1].low


def test_adx_high_in_trend_low_in_range():
    assert adx(uptrend(60), 14) > 25.0
    assert adx(flat_range(60), 14) < 25.0
    flat = [c(0, 100.0, 100.0, 100.0, 100.0)] * 30
    assert adx(flat, 14) == 0.0


def test_rsi_bounds_and_direction():
    assert rsi([float(x) for x in range(1, 40)], 14) > 70.0
    assert rsi([float(x) for x in range(40, 1, -1)], 14) < 30.0


def test_vol_ratio_positive():
    assert vol_ratio(uptrend(120), 14, 100) > 0.0
