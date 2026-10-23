from moonface.core.indicators import donchian_channel, rolling_std, sma
from moonface.core.models import Candle


def _c(h, lo, close):
    return Candle(0, close, h, lo, close, 0.0)


def test_donchian_channel_returns_prior_high_low_excluding_current():
    candles = [_c(10, 1, 5), _c(20, 2, 6), _c(30, 3, 7), _c(15, 4, 8)]
    # at i=3, prior window n=3 is bars 0..2: highs 10/20/30, lows 1/2/3
    hi, lo = donchian_channel(candles, 3, 3)
    assert hi == 30.0
    assert lo == 1.0


def test_sma_last_n_closes():
    assert sma([1.0, 2.0, 3.0, 4.0], 2) == 3.5


def test_rolling_std_population_of_last_n():
    # [2,4,4,4,5,5,7,9]: mean=5, population variance=4, std=2
    assert rolling_std([2.0, 4, 4, 4, 5, 5, 7, 9], 8) == 2.0


def test_rolling_std_uses_only_last_n():
    # only the last 2 values [10,12] count: mean=11, pop std=1
    assert rolling_std([0.0, 0.0, 0.0, 10.0, 12.0], 2) == 1.0


def test_rolling_std_zero_when_constant():
    assert rolling_std([5.0, 5.0, 5.0, 5.0], 4) == 0.0
