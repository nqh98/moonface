from dataclasses import dataclass

import pytest

from moonface.research.regime_overlay.overlay import (SIZE_RISKOFF_FACTOR,
                                                      apply_overlay)
from moonface.research.regime_overlay.regime import RegimeDef


@dataclass
class FakeCandle:
    timestamp_ms: int


@dataclass
class FakeTrade:
    side: str
    entry_index: int
    exit_index: int
    r_multiple: float


# regime depends only on entry timestamp: ts where (ts // 10) even -> risk_on
RON = RegimeDef("X", "x", lambda ts, m: (ts // 10) % 2 == 0)
CANDLES = [FakeCandle(timestamp_ms=i * 10) for i in range(10)]
# entry_index 0 -> ts 0 (risk_on); entry_index 1 -> ts 10 (risk_off)
TRADES = [
    FakeTrade("BUY", 0, 5, 2.0),    # risk_on
    FakeTrade("SELL", 1, 6, 1.0),   # risk_off
    FakeTrade("BUY", 1, 7, -0.5),   # risk_off
]


def test_directional_keeps_buy_in_riskon_and_sell_in_riskoff():
    out = apply_overlay(TRADES, CANDLES, RON, {}, "directional")
    # BUY@risk_on kept (2.0); SELL@risk_off kept (1.0); BUY@risk_off dropped
    assert out == [(50, 2.0), (60, 1.0)]


def test_derisk_drops_all_riskoff():
    out = apply_overlay(TRADES, CANDLES, RON, {}, "derisk")
    # only the risk_on trade survives
    assert out == [(50, 2.0)]


def test_size_scales_riskoff_keeps_all():
    out = apply_overlay(TRADES, CANDLES, RON, {}, "size")
    assert out[0] == (50, 2.0)
    assert out[1] == (60, round(1.0 * SIZE_RISKOFF_FACTOR, 6))
    assert out[2] == (70, round(-0.5 * SIZE_RISKOFF_FACTOR, 6))
    assert len(out) == 3


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        apply_overlay(TRADES, CANDLES, RON, {}, "bogus")
