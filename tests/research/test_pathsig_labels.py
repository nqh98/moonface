# tests/test_pathsig_labels.py
from moonface.core.models import Candle
from moonface.research.pathsig.labels import PathLabel, build_labels


def _candles(closes):
    # flat-range bars: high=low=close so excursions equal terminal moves
    return [Candle(timestamp_ms=i * 14_400_000, open=c, high=c, low=c,
                   close=c, volume=1.0) for i, c in enumerate(closes)]


def test_build_labels_returns_none_when_no_future_horizon():
    # NON-FLAT closes so ATR > 0: the only reason the tail is None is the
    # horizon guard (i + h >= len(candles)), not the zero-ATR branch.
    closes = [100.0 + (i % 3) for i in range(40)]
    candles = _candles(closes)
    labels = build_labels(candles, h=6, atr_period=14)
    assert len(labels) == len(candles)
    # positive anchor: a middle bar with >= h future bars and valid ATR,
    # proving the series is ATR-tradeable so the tail None-ness is horizon-caused
    assert labels[20] is not None
    # last h bars cannot have a forward label
    assert all(x is None for x in labels[-6:])


def test_label_matches_event_outcome_long_frame():
    closes = [100.0 + i for i in range(40)]  # steady uptrend
    candles = _candles(closes)
    labels = build_labels(candles, h=6, atr_period=14)
    # pick a middle bar with a valid label
    lbl = labels[20]
    assert isinstance(lbl, PathLabel)
    # uptrend held LONG: terminal forward move positive, no adverse excursion
    assert lbl.ret_r > 0
    assert lbl.mae_r <= 0.0
    assert lbl.mfe_r >= lbl.ret_r
    # direct contract: build_labels must forward event_outcome's tuple verbatim
    from moonface.research.drift_screen import event_outcome
    assert (lbl.ret_r, lbl.mae_r, lbl.mfe_r) == event_outcome(candles, 20, "LONG", 6, 14)
