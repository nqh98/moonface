from moonface.core.models import Candle
from moonface.research.playbook.config import PlaybookParams, WAIT, WATCH, LONG_SIGNAL
from moonface.research.playbook.mtf import MTFView
from moonface.research.playbook.engine import evaluate_bar, PLAYBOOK_NAME

H = 3_600_000


def _h1(prices):
    return [Candle(i * H, p, p + 0.3, p - 0.3, p, 1.0) for i, p in enumerate(prices)]


def _resample(h1, factor):
    out = []
    for k in range(0, len(h1), factor):
        chunk = h1[k:k + factor]
        out.append(Candle(chunk[0].timestamp_ms, chunk[0].open,
                          max(c.high for c in chunk), min(c.low for c in chunk),
                          chunk[-1].close, sum(c.volume for c in chunk)))
    return out


def test_downtrend_is_wait():
    h1 = _h1([100.0 - i * 0.005 for i in range(900)])
    v = MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))
    st = evaluate_bar(v, len(h1) - 1, PlaybookParams(), "atr_trail",
                      {"k_trail": 3.0, "max_bars": 96, "atr_period": 14})
    assert st.status == WAIT
    assert st.playbook == PLAYBOOK_NAME


def test_breakout_in_uptrend_is_long_signal():
    h1 = _h1([100.0 + i * 0.005 for i in range(900)] + [105.0])
    v = MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))
    st = evaluate_bar(v, len(h1) - 1, PlaybookParams(), "atr_trail",
                      {"k_trail": 3.0, "max_bars": 96, "atr_period": 14})
    assert st.status in (LONG_SIGNAL, WATCH)  # depends on quality; never WAIT in uptrend
    assert st.status != WAIT
