from moonface.core.models import Candle
from moonface.research.pathsig.data import (build_btc_dataset,
                                            cross_sectional_ranks,
                                            _trailing_return, _align_to_grid,
                                            resample_ohlc)
from moonface.research.pathsig.features import FEATURE_NAMES

H4 = 14_400_000
D1 = 86_400_000


def _bars(n, dur, start=0, base=100.0):
    return [Candle(timestamp_ms=start + i * dur, open=base + i,
                   high=base + i + 0.5, low=base + i - 0.5,
                   close=base + i, volume=1.0) for i in range(n)]


def test_resample_aggregates_complete_groups_only():
    base = _bars(13, H4)          # 13 4h bars: 2 full days (12) + 1 leftover
    daily = resample_ohlc(base, D1, H4)
    assert len(daily) == 2                      # the 13th bar's group is incomplete
    assert daily[0].timestamp_ms == 0
    assert daily[1].timestamp_ms == D1
    # closed-bar OHLC over the first 6 4h bars (indices 0..5)
    assert daily[0].open == base[0].open
    assert daily[0].close == base[5].close
    assert daily[0].high == max(b.high for b in base[:6])
    assert daily[0].low == min(b.low for b in base[:6])
    assert daily[0].volume == sum(b.volume for b in base[:6])


def test_resample_empty_input_returns_empty():
    assert resample_ohlc([], D1, H4) == []


def test_trailing_return_is_point_in_time():
    bars = _bars(5, H4, base=100.0)   # closes 100,101,102,103,104
    rets = _trailing_return(bars, 1)
    assert rets[0] is None
    assert rets[1] == 101.0 / 100.0 - 1.0


def test_align_to_grid_maps_by_timestamp():
    grid = [0, H4, 2 * H4]
    series = _bars(2, H4)             # timestamps 0, H4
    vals = [10.0, 20.0]
    aligned = _align_to_grid(grid, series, vals)
    assert aligned == [10.0, 20.0, None]


def test_rank_position_and_degenerate_bar():
    # bar 0: BTC=5 beats both peers -> 1.0 ; bar 1: BTC below both -> 0.0
    btc = [5.0, 1.0]
    peers = [[1.0, 9.0], [2.0, 8.0]]
    ranks = cross_sectional_ranks(btc, peers)
    assert ranks == [1.0, 0.0]


def test_rank_is_half_with_no_peers_or_missing_value():
    assert cross_sectional_ranks([5.0], [[None]]) == [0.5]   # no peers present
    assert cross_sectional_ranks([None], [[1.0]]) == [0.5]   # BTC value missing


def _synthetic_readers(n=500):
    # BTC + two peers, all on the same 4h grid; rising metrics so oi_z is defined.
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0, "SOLUSDT": 20.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_build_btc_dataset_yields_complete_samples():
    readers = _synthetic_readers(500)
    bundle, samples = build_btc_dataset(readers, h=6, atr_period=14,
                                        pool_symbols=["ETHUSDT", "SOLUSDT"])
    assert len(bundle.candles) == 500
    assert len(samples) > 50
    s = samples[0]
    assert len(s.x) == len(FEATURE_NAMES)
    assert all(v is not None for v in s.x)
    assert max(t.index for t in samples) < 500 - 6   # horizon excluded
