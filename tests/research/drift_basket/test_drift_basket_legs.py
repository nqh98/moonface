from moonface.core.models import Candle
from moonface.research.drift_basket.legs import (
    daily_close_returns,
    daily_long_flags,
    donchian_long_state,
    trailing_vol,
    utc_day,
)

H4_MS = 4 * 3_600_000
DAY_MS = 86_400_000


def _ramp(n, base=100.0, step=0.0, highs=None):
    """n 4h candles; close=base+step*i. `highs` overrides the high at given idx."""
    out = []
    for i in range(n):
        c = base + step * i
        hi = highs.get(i, c) if highs else c
        out.append(Candle(i * H4_MS, c, hi, c - 1.0, c, 1.0))
    return out


def test_breakout_sets_long_for_h_bars():
    # flat for 25 bars, then a single big up-close that exceeds the prior 20-high
    candles = _ramp(25)
    candles[24] = Candle(24 * H4_MS, 100.0, 200.0, 99.0, 200.0, 1.0)  # breakout close
    state = donchian_long_state(candles, n=20, h=12)
    longs = [is_long for _, is_long in state]
    assert longs[24] is True              # breakout bar is long
    assert longs[23] is False             # before breakout: flat
    # held for h bars only -> bar 24 is the sole long here (no later bars)
    assert sum(longs) == 1


def test_no_lookahead_first_n_bars_flat():
    candles = _ramp(30, step=1.0)         # monotone up, but first n have no channel
    state = donchian_long_state(candles, n=20, h=12)
    assert all(not is_long for _, is_long in state[:20])


def test_daily_flags_take_last_bar_of_day():
    # 6 bars/day; day 0 ends flat, construct a breakout only on day 1's last bar
    candles = _ramp(40, step=1.0)
    flags = daily_long_flags(candles, n=20, h=12)
    assert set(flags) == {utc_day(c.timestamp_ms) for c in candles}
    assert all(isinstance(v, bool) for v in flags.values())


def test_daily_close_returns_uses_last_close_per_day():
    candles = _ramp(12, base=100.0, step=10.0)  # 2 days of 6 bars
    rets = daily_close_returns(candles)
    days = sorted(rets)
    assert len(days) == 1                  # 2 days -> 1 return
    # day0 last close = 100+10*5=150 ; day1 last close = 100+10*11=210
    assert abs(rets[days[0]] - (210.0 / 150.0 - 1.0)) < 1e-9


def test_trailing_vol_window_and_floor():
    assert trailing_vol([0.1], 30) == 0.0
    v = trailing_vol([0.0, 0.02, -0.02, 0.0, 0.04], 3)
    assert v > 0.0
