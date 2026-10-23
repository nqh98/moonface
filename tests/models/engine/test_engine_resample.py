from moonface.core.models import Candle
from moonface.models.engine.resample import resample, resample_to_4h

H = 3_600_000
D = 24 * H
W = 7 * D
WEEK_ANCHOR = 345_600_000


def _c(ts, o=1.0, h=2.0, low=0.0, c=1.5, v=1.0):
    return Candle(ts, o, h, low, c, v)


def test_aggregates_aligned_groups_and_drops_partial():
    # 6 hourly candles starting at a 4h boundary (ts=0): one full 4h group
    # (ts 0..3) plus a partial group (ts 4,5) that must be dropped.
    candles = [_c(i * H, 10 + i, 20 + i, i, 12 + i) for i in range(6)]
    out = resample_to_4h(candles)
    assert len(out) == 1
    g = out[0]
    assert g.timestamp_ms == 0
    assert g.open == 10           # first.open
    assert g.close == 12 + 3      # last.close of the group
    assert g.high == 20 + 3       # max high in group
    assert g.low == 0             # min low in group
    assert g.volume == 4.0        # 4 hourly bars summed


def test_resample_4h_matches_wrapper_on_30_bar_fixture():
    candles = [
        _c(i * H, 100 + i, 200 + i, 50 - i, 150 + i, float(i + 1))
        for i in range(30)
    ]
    assert resample(candles, "4h") == resample_to_4h(candles)


def test_resample_1d_groups_24_and_drops_partial_trailing_day():
    candles = [
        _c(i * H, 100 + i, 200 + i, 50 - i, 150 + i, float(i + 1))
        for i in range(25)
    ]
    out = resample(candles, "1d")
    assert len(out) == 1
    day = out[0]
    assert day.timestamp_ms == 0
    assert day.open == candles[0].open
    assert day.high == max(c.high for c in candles[:24])
    assert day.low == min(c.low for c in candles[:24])
    assert day.close == candles[23].close
    assert day.volume == sum(c.volume for c in candles[:24])


def test_week_anchor_monday():
    # 2024-01-01 is a Monday. Bars Mon 00:00 .. Sun 23:00 = one full week.
    mon = 1_704_067_200_000
    bars = [_c(mon + i * H, 10 + i, 20 + i, i, 12 + i, float(i + 1)) for i in range(168)]
    wk = resample(bars, "1w")
    assert len(wk) == 1
    assert wk[0].timestamp_ms == mon


def test_sunday_bar_belongs_to_prior_week():
    mon = 1_704_067_200_000
    sunday_23 = mon + 6 * D + 23 * H
    week_start = ((sunday_23 - WEEK_ANCHOR) // W) * W + WEEK_ANCHOR
    assert week_start == mon
    bars = [_c(sunday_23)]
    wk = resample(bars, "1w")
    assert len(wk) == 0


def test_partial_week_dropped():
    mon = 1_704_067_200_000
    bars = [_c(mon + i * H) for i in range(167)]  # one bar short
    assert resample(bars, "1w") == []


def test_week_167_bar_group_is_dropped():
    mon = 1_704_067_200_000
    bars = [_c(mon + i * H, 10 + i, 30 + i, 5 - i, 15 + i, float(i + 1)) for i in range(167)]
    assert resample(bars, "1w") == []


def test_week_ohlcv_aggregation_correctness():
    mon = 1_704_067_200_000
    bars = [
        _c(mon + i * H, o, h, low, c, v)
        for i, (o, h, low, c, v) in enumerate([
            (10, 12, 9, 11, 1.5),
            (11, 15, 8, 14, 2.5),
            (14, 16, 7, 13, 3.5),
            (13, 18, 6, 17, 4.5),
            (17, 19, 5, 18, 5.5),
            (18, 20, 4, 19, 6.5),
            (19, 21, 3, 20, 7.5),
        ] * 24)
    ]
    wk = resample(bars, "1w")
    assert len(wk) == 1
    got = wk[0]
    assert got.open == bars[0].open
    assert got.high == max(b.high for b in bars)
    assert got.low == min(b.low for b in bars)
    assert got.close == bars[-1].close
    assert got.volume == sum(b.volume for b in bars)


def test_too_short_returns_empty():
    assert resample_to_4h([_c(0)]) == []
