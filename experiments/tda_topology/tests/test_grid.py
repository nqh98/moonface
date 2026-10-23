import math

import pytest

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle

from grid import build_grid, load_pool_cache_only, log_return_matrix


def _candle(ts, close):
    return Candle(timestamp_ms=ts, open=close, high=close,
                  low=close, close=close, volume=1.0)


def _bundle(pairs):
    return DataBundle(candles=[_candle(ts, c) for ts, c in pairs])


def test_grid_is_sorted_union_of_bar_timestamps():
    pool = {"A": _bundle([(300, 1.0), (100, 1.0)]),
            "B": _bundle([(200, 1.0), (100, 1.0)])}
    assert build_grid(pool) == [100, 200, 300]


def test_returns_are_log_and_aligned_to_the_grid():
    pool = {"A": _bundle([(100, 1.0), (200, 2.0), (300, 4.0)])}
    ts = build_grid(pool)
    rets = log_return_matrix(pool, ts)
    assert rets["A"][0] is None                       # no prior bar
    assert rets["A"][1] == pytest.approx(math.log(2))
    assert rets["A"][2] == pytest.approx(math.log(2))


def test_missing_bar_yields_none_not_a_silent_gap():
    # B has no bar at 200; its return there must be None, and the return at
    # 300 must also be None because the previous *B* bar is not adjacent.
    pool = {"A": _bundle([(100, 1.0), (200, 2.0), (300, 4.0)]),
            "B": _bundle([(100, 1.0), (300, 4.0)])}
    ts = build_grid(pool)
    rets = log_return_matrix(pool, ts)
    assert rets["B"][1] is None
    assert rets["B"][2] is None


def test_missing_symbol_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError, match="NOPEUSDT"):
        load_pool_cache_only(str(tmp_path), ["NOPEUSDT"])
