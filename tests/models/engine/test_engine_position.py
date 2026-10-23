# tests/test_engine_position.py
import pytest

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.position import (CT_MAX_BARS, CT_STOP_ATR, CT_TARGET_R,
                                             PositionState, _net_r, manage_position,
                                             open_position, reconstruct)

H = 3_600_000


def _flat_series(n, price=100.0, spread=2.0):
    return [Candle(i * H, price, price + spread, price - spread, price, 1.0)
            for i in range(n)]


def _cfg(**kw):
    base = dict(atr_period=5, k_stop=2.0, k_trail=3.0, max_bars=96,
                base_fraction=0.005, max_fraction=0.02)
    base.update(kw)
    return EngineConfig(**base)


def test_open_long_sets_stop_below():
    candles = _flat_series(30)
    res = open_position(candles, _cfg(), direction=1, confidence=0.8,
                        fraction=0.01)
    assert res.action == "OPEN"
    assert res.direction == 1
    assert res.stop < res.entry_price
    assert res.invalidation == res.stop
    assert res.atr_frac is not None and res.atr_frac > 0


def test_reconstruct_none_when_flat_or_exited():
    assert reconstruct([], "v1") is None
    exited = [{"strategy_version": "v1", "status": "engine", "action": "EXIT"}]
    assert reconstruct(exited, "v1") is None


def test_reconstruct_open_position():
    entries = [{"strategy_version": "v1", "status": "engine", "action": "OPEN",
                "decision": "LONG", "entry_price": 100.0, "stop": 96.0,
                "extreme": 100.0, "atr_at_entry": 2.0, "fraction": 0.01,
                "bars_held": 0}]
    pos = reconstruct(entries, "v1")
    assert pos == PositionState(1, 100.0, 96.0, 100.0, 2.0, 0.01, 0)


def test_manage_stop_hit_exits_at_stop():
    cfg = _cfg()
    candles = _flat_series(30)
    # open long at 100 with stop ~96, then a candle that pierces 96
    pos = PositionState(1, 100.0, 96.0, 100.0, 2.0, 0.01, 0)
    drop = Candle(31 * H, 100.0, 100.0, 95.0, 95.5, 1.0)
    res = manage_position(candles + [drop], cfg, pos, signal_direction=1,
                          confidence=0.8)
    assert res.action == "EXIT"
    # realized R ~ (96-100)/2 = -2, minus cost
    assert res.realized_r < -1.9


def test_manage_hold_ratchets_stop_up():
    cfg = _cfg()
    candles = _flat_series(30)
    pos = PositionState(1, 100.0, 96.0, 100.0, 2.0, 0.01, 0)
    up = Candle(31 * H, 100.0, 110.0, 100.0, 109.0, 1.0)
    res = manage_position(candles + [up], cfg, pos, signal_direction=1,
                          confidence=0.8)
    assert res.action == "HOLD"
    assert res.stop > 96.0          # ratcheted toward price
    assert res.bars_held == 1


def test_manage_reversal_exits():
    # v2: reversal fires purely on an opposite signal_direction, with NO
    # confidence floor. confidence=0.0 must still reverse.
    cfg = _cfg()
    candles = _flat_series(30)
    pos = PositionState(1, 100.0, 96.0, 100.0, 2.0, 0.01, 0)
    flat = Candle(31 * H, 100.0, 101.0, 99.0, 100.0, 1.0)
    res = manage_position(candles + [flat], cfg, pos, signal_direction=-1,
                          confidence=0.0)
    assert res.action == "EXIT"
    assert "reversal" in res.reason.lower()


def test_manage_no_reversal_when_signal_flat():
    # signal_direction == 0 (no SETUP) must NOT reverse, regardless of confidence
    cfg = _cfg()
    candles = _flat_series(30)
    pos = PositionState(1, 100.0, 96.0, 100.0, 2.0, 0.01, 0)
    flat = Candle(31 * H, 100.0, 101.0, 99.0, 100.0, 1.0)
    res = manage_position(candles + [flat], cfg, pos, signal_direction=0,
                          confidence=0.9)
    assert res.action == "HOLD"


def test_open_position_defaults_to_wt_profile():
    # backward-compat: the old 5-positional-arg call still means a WT open
    candles = _flat_series(30)
    res = open_position(candles, _cfg(), direction=1, confidence=0.8,
                        fraction=0.01)
    assert res.profile == "WT"
    assert res.target is None


def test_open_ct_long_stop_from_wick_not_entry():
    candles = _flat_series(30)
    res = open_position(candles, _cfg(), direction=1, confidence=0.8,
                        fraction=0.0075, profile="CT", sweep_wick=90.0)
    assert res.action == "OPEN"
    assert res.profile == "CT"
    a = res.atr_at_entry
    assert res.stop == 90.0 - CT_STOP_ATR * a
    fallback_stop = res.entry_price - CT_STOP_ATR * a
    assert res.stop != fallback_stop
    assert res.target == res.entry_price + CT_TARGET_R * a


def test_open_ct_short_stop_from_wick_not_entry():
    candles = _flat_series(30)
    res = open_position(candles, _cfg(), direction=-1, confidence=0.8,
                        fraction=0.0075, profile="CT", sweep_wick=110.0)
    assert res.profile == "CT"
    a = res.atr_at_entry
    assert res.stop == 110.0 + CT_STOP_ATR * a
    assert res.target == res.entry_price - CT_TARGET_R * a


def test_open_ct_falls_back_to_entry_when_no_sweep_wick():
    candles = _flat_series(30)
    res = open_position(candles, _cfg(), direction=1, confidence=0.8,
                        fraction=0.0075, profile="CT", sweep_wick=None)
    a = res.atr_at_entry
    assert res.stop == res.entry_price - CT_STOP_ATR * a


def test_manage_ct_target_fill_exits_at_net_r():
    cfg = _cfg()
    entry, a = 100.0, 2.0
    target = entry + CT_TARGET_R * a
    pos = PositionState(1, entry, 95.0, entry, a, 0.0075, 0, "CT", target)
    candles = _flat_series(30)
    bar = Candle(31 * H, 100.0, target + 1.0, 99.0, 103.0, 1.0)
    res = manage_position(candles + [bar], cfg, pos, signal_direction=1,
                          confidence=0.8)
    assert res.action == "EXIT"
    assert res.price == target
    assert res.realized_r == _net_r(pos, target)
    assert res.realized_r == pytest.approx(2.0, abs=0.1)


def test_manage_ct_stop_before_target_pessimism():
    cfg = _cfg()
    entry, a, stop = 100.0, 2.0, 95.0
    target = entry + CT_TARGET_R * a
    pos = PositionState(1, entry, stop, entry, a, 0.0075, 0, "CT", target)
    candles = _flat_series(30)
    # single bar's range spans both the stop and the target
    bar = Candle(31 * H, 100.0, target + 1.0, stop - 1.0, 100.0, 1.0)
    res = manage_position(candles + [bar], cfg, pos, signal_direction=1,
                          confidence=0.8)
    assert res.action == "EXIT"
    assert res.price == stop
    assert res.realized_r < 0


def test_manage_ct_no_trail_on_favorable_bar():
    cfg = _cfg()
    entry, a, stop = 100.0, 2.0, 95.0
    target = entry + CT_TARGET_R * a
    pos = PositionState(1, entry, stop, entry, a, 0.0075, 0, "CT", target)
    candles = _flat_series(30)
    up = Candle(31 * H, 100.0, 102.0, 99.0, 101.5, 1.0)
    res = manage_position(candles + [up], cfg, pos, signal_direction=1,
                          confidence=0.8)
    assert res.action == "HOLD"
    assert res.invalidation == pos.stop
    assert res.stop == pos.stop
    assert res.target == pos.target


def test_manage_ct_time_stop_at_24_bars():
    cfg = _cfg()
    entry, a, stop = 100.0, 2.0, 95.0
    target = entry + CT_TARGET_R * a
    pos = PositionState(1, entry, stop, entry, a, 0.0075, CT_MAX_BARS - 1,
                        "CT", target)
    candles = _flat_series(30)
    bar = Candle(31 * H, 100.0, 101.0, 99.0, 100.5, 1.0)  # benign, no fill
    res = manage_position(candles + [bar], cfg, pos, signal_direction=1,
                          confidence=0.8)
    assert res.action == "EXIT"
    assert res.bars_held == CT_MAX_BARS
    assert res.price == bar.close


def test_manage_ct_reversal_exits():
    # v2: CT reversal also fires purely on opposite signal_direction (no floor)
    cfg = _cfg()
    entry, a, stop = 100.0, 2.0, 95.0
    target = entry + CT_TARGET_R * a
    pos = PositionState(1, entry, stop, entry, a, 0.0075, 0, "CT", target)
    candles = _flat_series(30)
    bar = Candle(31 * H, 100.0, 101.0, 99.0, 100.0, 1.0)
    res = manage_position(candles + [bar], cfg, pos, signal_direction=-1,
                          confidence=0.0)
    assert res.action == "EXIT"
    assert "reversal" in res.reason.lower()


def test_manage_ct_none_target_holds_without_raising():
    # a malformed CT journal entry with no target must degrade to a no-target
    # HOLD rather than raising on the target comparison / format
    cfg = _cfg()
    entry, a, stop = 100.0, 2.0, 95.0
    pos = PositionState(1, entry, stop, entry, a, 0.0075, 0, "CT", None)
    candles = _flat_series(30)
    bar = Candle(31 * H, 100.0, 101.0, 99.0, 100.0, 1.0)
    res = manage_position(candles + [bar], cfg, pos, signal_direction=1,
                          confidence=0.0)
    assert res.action == "HOLD"
    assert res.target is None
    assert "no target" in res.reason.lower()


def test_reconstruct_round_trips_ct_profile_and_target():
    entries = [{"strategy_version": "v1", "status": "engine", "action": "OPEN",
                "decision": "LONG", "entry_price": 100.0, "stop": 95.0,
                "extreme": 100.0, "atr_at_entry": 2.0, "fraction": 0.0075,
                "bars_held": 0, "profile": "CT", "target": 104.0}]
    pos = reconstruct(entries, "v1")
    assert pos == PositionState(1, 100.0, 95.0, 100.0, 2.0, 0.0075, 0, "CT", 104.0)


def test_reconstruct_excludes_mismatched_version_entry():
    # an older-schema entry tagged with a different strategy_version must not
    # be reconstructed against the current version, proving version isolation
    entries = [{"strategy_version": "v0", "status": "engine", "action": "OPEN",
                "decision": "LONG", "entry_price": 100.0, "stop": 96.0,
                "extreme": 100.0, "atr_at_entry": 2.0, "fraction": 0.01,
                "bars_held": 0, "profile": "CT", "target": 104.0}]
    assert reconstruct(entries, "v1") is None
