"""Tests for the four frozen portfolio combination operators."""
from moonface.core.models import Candle
from moonface.research.portfolio.operators import (
    long_short_net,
    regime_switch,
    vote,
    vol_target,
)


def test_vote_majority():
    pos = [[1, 1, -1, 0], [1, -1, -1, 0], [1, 1, 1, 1]]  # 3 comps, 4 bars
    out = vote(pos, "majority")  # thresh = 2
    assert out == [1.0, 1.0, -1.0, 0.0]  # bar0: 3 long; bar1: 2 long; bar2: 2 short; bar3: 1 long<2 -> 0


def test_vote_k_of_n():
    pos = [[1, -1, 0], [0, -1, 0], [-1, -1, 1]]
    out = vote(pos, 2)
    assert out == [0.0, -1.0, 0.0]  # bar1: 3 short>=2


def test_long_short_net_clipped():
    pos = [[1, -1], [1, -1], [1, 1]]
    out = long_short_net(pos)
    assert out[0] == 1.0   # net=3 -> clip 1
    assert out[1] == -1.0  # net=-1


def test_vol_target_scales_by_inverse_vol():
    # out[t] = base[t] * target_vol / realized_vol (causal window up to t).
    import math
    abr = [0.5, -0.5, 0.5, -0.5, 0.5]
    base = [1.0, 1.0, 1.0, 1.0, 1.0]
    out = vol_target(base, abr, target_vol=1.0, vol_lookback=4)
    # at t=4 the causal window is abr[0:5]; sample std (ddof=1), matching _std
    w = abr[0:5]
    m = sum(w) / len(w)
    rv = math.sqrt(sum((x - m) ** 2 for x in w) / (len(w) - 1))
    expected = base[-1] * (1.0 / rv)        # base * target_vol / rv
    assert abs(out[-1] - expected) < 1e-9   # tight: catches a formula inversion


def test_regime_switch_flats_in_range():
    candles = [Candle(timestamp_ms=t * 3_600_000, open=p, high=p, low=p,
                       close=p, volume=1.0)
                for t, p in enumerate([100 + 10 * t for t in range(60)])]  # strong uptrend
    pos = [[1] * 60, [1] * 60]
    out = regime_switch(pos, candles, floor=0.10, lookback=50)
    assert all(p >= 0 for p in out)
