from moonface.core.indicators import ema


def test_ema_constant_series_returns_constant():
    assert ema([5.0] * 10, 5) == 5.0


def test_ema_seeds_on_first_value():
    # single element: EMA is that element
    assert ema([42.0], 5) == 42.0


def test_ema_tracks_a_rising_series_below_last_value():
    closes = [float(x) for x in range(1, 21)]  # 1..20 rising
    e = ema(closes, 5)
    # EMA of a rising series lags below the last value but above the midpoint tail
    assert e < closes[-1]
    assert e > closes[-5]


def test_ema_weights_recent_more_than_sma():
    closes = [10.0] * 9 + [20.0]  # a late jump
    # EMA reacts to the jump more than a flat-weight mean of 11.0
    assert ema(closes, 5) > 11.0
