from moonface.core.models import Candle
from moonface.research.playbook.config import (PlaybookParams, UPTREND, DOWNTREND,
                                               NO_TRADE, OVEREXTENDED)
from moonface.research.playbook.regime import classify_regime

H4 = 4 * 3_600_000


def _series(prices, spread=2.5):
    return [Candle(i * H4, p, p + spread, p - spread, p, 1.0) for i, p in enumerate(prices)]


def test_insufficient_history_is_no_trade():
    assert classify_regime(_series([100] * 10), PlaybookParams()) == NO_TRADE


def test_steady_rise_is_uptrend():
    prices = [100 + i * 0.5 for i in range(260)]   # smooth, persistent uptrend
    assert classify_regime(_series(prices), PlaybookParams()) == UPTREND


def test_steady_fall_is_downtrend():
    prices = [300 - i * 0.5 for i in range(260)]
    assert classify_regime(_series(prices), PlaybookParams()) == DOWNTREND


def test_sharp_spike_above_mid_is_overextended():
    prices = [100 + i * 0.2 for i in range(259)] + [400.0]  # final blow-off
    assert classify_regime(_series(prices), PlaybookParams()) == OVEREXTENDED
