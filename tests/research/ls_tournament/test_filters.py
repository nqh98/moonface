"""Filter alignment tests: funding/OI are timestamp-keyed (ts, value) series and
must be aligned to candles by timestamp (as-of, no lookahead), never indexed by
candle position. These guard the bug where raw (ts, rate) tuples were compared
to floats and where sub-window slicing corrupted the external series."""
from moonface.core.models import Candle
from moonface.research.ls_tournament import explore


def _candles(n, tf_ms=7_200_000):
    return [Candle(timestamp_ms=k * tf_ms, open=100.0, high=101.0,
                   low=99.0, close=100.0, volume=1.0) for k in range(n)]


def test_funding_extreme_aligns_tuple_points():
    candles = _candles(10)
    entries = [(i, "LONG") for i in range(10)] + [(i, "SHORT") for i in range(10)]
    # 8h funding cadence (every 4th 2h bar); strongly positive => crowded longs.
    points = [(k * 7_200_000 * 4, 0.001) for k in range(3)]
    ctx = {"funding": points}
    kept = explore._apply_funding_extreme(candles, entries, ctx, {"thr": 0.0005})
    # No crash on tuples, and only SHORT survives extreme-positive funding.
    assert kept, "expected some entries to survive"
    assert all(side == "SHORT" for _, side in kept)


def test_funding_extreme_no_points_passthrough():
    candles = _candles(5)
    entries = [(0, "LONG"), (1, "SHORT")]
    assert explore._apply_funding_extreme(candles, entries, {"funding": []}, {"thr": 0.0005}) == entries


def test_oi_momentum_aligns_and_does_not_crash():
    candles = _candles(60)
    entries = [(i, "LONG") for i in range(60)]
    # Rising OI snapshots at 2h cadence.
    points = [(k * 7_200_000, 1000.0 + k * 5.0) for k in range(60)]
    ctx = {"oi_points": points}
    kept = explore._apply_oi_momentum(candles, entries, ctx,
                                      {"window": 10, "lookback": 3, "z_thr": 0.5})
    assert isinstance(kept, list)
    assert all(side == "LONG" for _, side in kept)


def test_slice_context_leaves_timestamp_keyed_whole():
    ctx = {
        "funding": [(0, 0.1), (1, 0.2), (2, 0.3)],
        "macro": {"SP500": [(0, 1.0), (1, 2.0)]},
        "oi_points": [(0, 10.0), (1, 11.0)],
        "per_bar": [1, 2, 3, 4, 5],
    }
    sliced = explore._slice_context(ctx, 3, 5)
    assert sliced["funding"] == ctx["funding"]            # not index-sliced
    assert sliced["macro"] == ctx["macro"]
    assert sliced["oi_points"] == ctx["oi_points"]
    assert sliced["per_bar"] == [4, 5]                    # ordinary per-bar list IS sliced
