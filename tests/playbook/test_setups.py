# tests/playbook/test_setups.py
from moonface.core.models import Candle
from moonface.research.playbook.config import PlaybookParams, UPTREND
from moonface.research.playbook.setups import detect_setup, Setup

H = 3_600_000


def _series(prices):
    out = []
    for i, p in enumerate(prices):
        out.append(Candle(i * H, p, p + 0.3, p - 0.3, p, 1.0))
    return out


def _h2_up():
    return _series([100 + i for i in range(60)])


def test_trend_breakout_triggers_on_new_donchian_high():
    # 60 flat bars then a decisive close above the prior-20 high
    prices = [100.0] * 60 + [105.0]
    s = detect_setup(_series(prices), _h2_up(), UPTREND, PlaybookParams())
    assert isinstance(s, Setup)
    assert s.name == "trend_breakout"
    assert s.phase == "triggered"
    assert s.entry == 105.0


def test_no_setup_when_price_inside_channel():
    prices = [50.0] * 80  # flat market, no break
    s = detect_setup(_series(prices), _h2_up(), UPTREND, PlaybookParams())
    assert s is None


def test_failed_breakdown_reclaim_detected():
    # establish a range low ~95, break below it, then close back above
    prices = [100.0] * 40 + [95.0] * 20 + [94.0] + [97.0]
    s = detect_setup(_series(prices), _h2_up(), UPTREND, PlaybookParams())
    assert s is not None and s.name == "failed_breakdown_reclaim"
