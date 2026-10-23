# tests/playbook/test_quality.py
from moonface.core.models import Candle
from moonface.research.playbook.config import (PlaybookParams, UPTREND, OVEREXTENDED)
from moonface.research.playbook.setups import Setup, TRIGGERED
from moonface.research.playbook.quality import quality_check

H = 3_600_000


def _series(prices):
    return [Candle(i * H, p, p + 0.5, p - 0.5, p, 1.0) for i, p in enumerate(prices)]


def test_post_exhaustion_rejects():
    s = Setup("trend_breakout", TRIGGERED, 105.0, 100.0, 104.0)
    q = quality_check(_series([100 + i * 0.1 for i in range(120)]), s, OVEREXTENDED,
                      PlaybookParams())
    assert not q.passed and "post_exhaustion" in q.reasons


def test_entry_far_from_invalidation_rejects():
    # invalidation 50 below a 105 entry, ATR ~1 => risk >> max_risk_atr
    s = Setup("trend_breakout", TRIGGERED, 105.0, 55.0, 104.0)
    q = quality_check(_series([100 + i * 0.1 for i in range(120)]), s, UPTREND,
                      PlaybookParams())
    assert not q.passed and "entry_far_from_invalidation" in q.reasons


def test_clean_breakout_passes():
    s = Setup("trend_breakout", TRIGGERED, 112.0, 111.0, 111.5)
    q = quality_check(_series([100 + i * 0.1 for i in range(120)]), s, UPTREND,
                      PlaybookParams())
    assert q.passed and q.reasons == []
