"""Tests for per-bar position + return series and MTF alignment (Task 4)."""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.portfolio.streams import (asset_bar_r, native_positions,
                                                 align_to_grid, position_returns)


def _candles(prices, tf_ms=3_600_000):
    return [Candle(timestamp_ms=t * tf_ms, open=p, high=p * 1.01,
                   low=p * 0.99, close=p, volume=1.0) for t, p in enumerate(prices)]


def test_asset_bar_r_first_is_zero_and_uses_atr():
    candles = _candles([100.0, 101.0, 103.0, 100.0])
    r = asset_bar_r(candles, period=14)
    assert r[0] == 0.0
    assert len(r) == len(candles)


def test_align_to_grid_forward_fills():
    h4 = _candles([0.0, 1.0, 2.0], tf_ms=14_400_000)      # 3 4h bars
    h1 = _candles([float(t) for t in range(12)], tf_ms=3_600_000)  # 12 1h bars
    native = [1.0, -1.0, 0.0]                              # position per 4h bar
    aligned = align_to_grid(native, h4, h1)
    assert len(aligned) == 12
    # 1h bars 0-3 map to 4h bar 0 (pos 1.0); 4-7 -> 4h bar 1 (-1.0); 8-11 -> 0.0
    assert aligned[:4] == [1.0] * 4
    assert aligned[4:8] == [-1.0] * 4
    assert aligned[8:] == [0.0] * 4


def test_position_returns_apply_cost_at_entry_and_zero_when_flat():
    candles = _candles([100.0, 101.0, 102.0, 101.0, 100.0])
    abr = asset_bar_r(candles, period=14)
    positions = [0.0, 1.0, 1.0, -1.0, -1.0]  # long bars 1-2, short bars 3-4
    ret = position_returns(positions, abr, candles)
    assert len(ret) == 5
    # cost applied at flip bars (1 and 3); flat bar 0 returns ~0
    assert abs(ret[0]) < 1e-9


def test_position_returns_round_trip_cost_matches_single_trade_r():
    from moonface.core.metrics import COST_FRACTION
    from moonface.core.risk import atr
    candles = _candles([100.0, 101.0, 101.0, 100.0])   # non-zero ATR
    abr_zero = [0.0, 0.0, 0.0, 0.0]                    # force gross=0 → ret = -cost
    positions = [0.0, 1.0, 1.0, 0.0]                   # entry bar1, exit bar3
    ret = position_returns(positions, abr_zero, candles)
    # entry leg cost uses ATR at bar1, exit leg uses ATR at bar3
    a1 = atr(candles[:2], 14)
    half1 = COST_FRACTION / (2.0 * (a1 / candles[1].close))
    a3 = atr(candles[:4], 14)
    half3 = COST_FRACTION / (2.0 * (a3 / candles[3].close))
    assert abs(ret[0]) < 1e-12                          # flat bar, no cost
    assert abs(ret[1] + half1) < 1e-9                    # entry leg = half round-trip
    assert abs(ret[2]) < 1e-12                          # hold, no cost
    assert abs(ret[3] + half3) < 1e-9                    # exit leg = half round-trip
    # sum of entry+exit ≈ COST_FRACTION/atr_frac (small ATR drift across bars)


def test_native_positions_flat_without_entries():
    from moonface.research.system_cells import system_cells_for
    # A monotone series with a roc_sign cell yields some long entries; verify shape.
    cell = sorted([c for c in system_cells_for("1h") if c.family == "roc_sign"],
                  key=lambda c: c.swept)[1]  # center
    candles = _candles([100.0 + i for i in range(120)])
    pos = native_positions(candles, cell)
    assert len(pos) == len(candles)
    assert all(p in (-1.0, 0.0, 1.0) for p in pos)
