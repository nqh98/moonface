from __future__ import annotations

from moonface.core.models import Candle
from moonface.feed.levels import Levels
from moonface.feed.setups import Setup
from moonface.feed.state import (is_open, open_setup, resolve_open, setup_hash)


def _long():
    return Setup("sweep_choch", "LONG", 70, 100.0, 90.0, 95.0, 4.0)


def _levels():
    return Levels(100.0, 99.0, 101.0, 90.0, 110.0, 120.0, 130.0, 0.80)


def _c(ts, lo, hi):
    return Candle(ts, (lo + hi) / 2, hi, lo, (lo + hi) / 2, 1.0)


def test_setup_hash_is_stable_and_level_aware(tmp_path):
    s = _long()
    assert setup_hash(s) == setup_hash(s)
    other = Setup("sweep_choch", "SHORT", 70, 100.0, 110.0, 105.0, 4.0)
    assert setup_hash(other) != setup_hash(s)


def test_is_open_and_open_setup_one_per_symbol(tmp_path):
    p = tmp_path / "feed.jsonl"
    assert is_open(p, "BTC/USDT:USDT") is False
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=1_000)
    assert is_open(p, "BTC/USDT:USDT") is True
    # a second open for the same symbol is still "open" (caller suppresses it)
    assert is_open(p, "BTC/USDT:USDT") is True


def test_resolve_open_marks_stop_when_low_breaks(tmp_path):
    p = tmp_path / "feed.jsonl"
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=0)
    # entry 100, stop 90, tp1 110. A later candle with low 88 hits the stop.
    candles = [_c(0, 99, 101), _c(4_000, 88, 95)]
    closed = resolve_open(p, candles, tf_ms=4_000)
    assert len(closed) == 1
    assert closed[0]["outcome"] == "SL"
    assert closed[0]["realized_r"] < 0
    assert is_open(p, "BTC/USDT:USDT") is False


def test_resolve_open_marks_tp1_when_high_breaks(tmp_path):
    p = tmp_path / "feed.jsonl"
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=0)
    candles = [_c(0, 99, 101), _c(4_000, 111, 115)]   # high 111 > tp1 110
    closed = resolve_open(p, candles, tf_ms=4_000)
    assert closed[0]["outcome"] == "TP"
    assert closed[0]["realized_r"] > 0


def test_resolve_open_timeout_when_neither_hit(tmp_path):
    p = tmp_path / "feed.jsonl"
    open_setup(p, "BTC/USDT:USDT", _long(), _levels(), candle_ts_ms=0)
    # 30 bars later, price still inside the range -> timeout (no tp/sl).
    candles = [_c(i * 4_000, 95, 105) for i in range(31)]
    closed = resolve_open(p, candles, tf_ms=4_000, max_bars=30)
    assert closed[0]["outcome"] == "TIMEOUT"
    assert is_open(p, "BTC/USDT:USDT") is False
