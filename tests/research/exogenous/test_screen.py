from __future__ import annotations

from moonface.research.exogenous.screen import (
    newey_west_t, conditional_series, screen_passes, SCREEN_T)


def test_newey_west_t_zero_for_zero_mean():
    assert abs(newey_west_t([1.0, -1.0, 1.0, -1.0, 1.0, -1.0])) < 0.5


def test_newey_west_t_large_for_strong_signal():
    assert newey_west_t([0.02] * 40) > 5.0  # constant positive -> huge t


def test_conditional_series_applies_sign_and_mask():
    out = conditional_series([True, False, True], sign=-1, fwd_ret=[0.01, 0.5, -0.02])
    assert out == [-0.01, 0.02]


def test_screen_passes_threshold():
    assert SCREEN_T == 2.0
    assert screen_passes([{"t": 0.3}, {"t": -2.5}]) is True
    assert screen_passes([{"t": 0.3}, {"t": 1.1}]) is False
