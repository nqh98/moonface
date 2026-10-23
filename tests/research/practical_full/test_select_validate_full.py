"""The practical-full lane adds a 2x/3x multiplicative cost gate on top of the
reused practical select/validate. These tests pin that the extra gate (a) is
applied and (b) can drop an otherwise-passing candidate."""
from moonface.core.models import Candle
from moonface.research import system_battery as sb
from moonface.research.practical_full import grid, select_full, validate_full

import pytest

pytestmark = pytest.mark.slow


def _series(n):
    """Uptrend with periodic thrust bars that actually break the ATR channel
    (a flat ramp never does), so net_trade_rs yields real, profitable trades."""
    out, px = [], 1000.0
    for k in range(n):
        thrust = 40.0 if k % 6 == 0 else 0.0
        px = px * 1.0008 + thrust
        out.append(Candle(timestamp_ms=k * 14_400_000, open=px - 4, high=px + 8,
                          low=px - 8, close=px, volume=1.0))
    return out


def _trend_rows(cs):
    from moonface.research.practical.explore import run_explore
    cfgs = [c for c in grid.configs_for("4h") if c.family == "atr_channel_break"]
    return run_explore(cfgs, {"4h": cs}), cfgs


def test_select_full_keeps_clean_trend_with_cost_multiple_checks():
    cs = _series(4000)
    rows, _ = _trend_rows(cs)
    survivors = select_full.select_full(rows, {"4h": cs})
    assert survivors, "a clean strong trend should survive"
    for s in survivors:
        assert s["selection"]["checks"]["cost_2x"] is True
        assert s["selection"]["checks"]["cost_3x"] is True


def test_select_full_drops_candidate_when_3x_cost_fails(monkeypatch):
    cs = _series(4000)
    rows, _ = _trend_rows(cs)
    baseline = select_full.select_full(rows, {"4h": cs})
    assert baseline  # would otherwise survive

    real = sb.cost_multiple_ok

    def fake(candles, family, params, exit_name, exit_params, h, mult):
        res = real(candles, family, params, exit_name, exit_params, h, mult)
        if mult == 3.0:
            return {**res, "passed": False}
        return res
    monkeypatch.setattr(select_full.sb, "cost_multiple_ok", fake)
    assert select_full.select_full(rows, {"4h": cs}) == []


def test_validate_full_requires_cost_multiple_on_both_segments():
    cs = _series(4000)
    val, sealed = cs[:2000], cs[2000:]
    row = {"timeframe": "4h", "family": "atr_channel_break",
           "params": {"k": 1.0, "atr_period": 14}, "exit_name": "atr_trail",
           "exit_params": {"k_trail": 2.0, "max_bars": 120, "atr_period": 14},
           "h": 48}
    res = validate_full.validate_candidate_full(row, val, sealed)
    assert res["verdict"] == "paper_accept"
    assert res["validate"]["cost_2x_ok"] and res["validate"]["cost_3x_ok"]
    assert res["sealed"]["cost_2x_ok"] and res["sealed"]["cost_3x_ok"]


def test_validate_full_rejects_when_cost_multiple_fails(monkeypatch):
    cs = _series(4000)
    val, sealed = cs[:2000], cs[2000:]
    row = {"timeframe": "4h", "family": "atr_channel_break",
           "params": {"k": 1.0, "atr_period": 14}, "exit_name": "atr_trail",
           "exit_params": {"k_trail": 2.0, "max_bars": 120, "atr_period": 14},
           "h": 48}
    real = sb.cost_multiple_ok

    def fake(candles, family, params, exit_name, exit_params, h, mult):
        res = real(candles, family, params, exit_name, exit_params, h, mult)
        return {**res, "passed": False} if mult == 3.0 else res
    monkeypatch.setattr(validate_full.sb, "cost_multiple_ok", fake)
    res = validate_full.validate_candidate_full(row, val, sealed)
    assert res["verdict"] == "rejected"
