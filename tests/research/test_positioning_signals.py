# tests/test_positioning_signals.py
import pytest

from moonface.research.edge.positioning_signals import (
    make_oi_build_momentum,
    make_oi_flush_reversal,
    make_taker_flow_momentum,
    make_toptrader_follow,
)
from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries

_H4_MS = 4 * 3_600_000
N = 320
PARAMS_CHANGE = {"window": 180, "lookback": 12, "z_thr": 1.5}
PARAMS_LEVEL = {"window": 180, "z_thr": 1.5}


def _candles(closes):
    return [Candle(i * _H4_MS, c, c * 1.01, c * 0.99, c, 1.0)
            for i, c in enumerate(closes)]


def _flat_oi(n=N):
    return [1000.0 + (i % 5) * 0.1 for i in range(n)]  # boring wiggle


def _flush_tail(n=N, drop=0.97):
    """Stable OI, then a violent deleveraging drop over the last 20 bars."""
    oi = _flat_oi(n)
    for i in range(n - 20, n):
        oi[i] = oi[i - 1] * drop
    return oi


def test_oi_flush_reversal_longs_when_price_fell_with_oi():
    closes = [100.0] * (N - 20) + [100.0 * (0.99 ** k) for k in range(1, 21)]
    entries = make_oi_flush_reversal(_flush_tail())(_candles(closes),
                                                    PARAMS_CHANGE)
    assert entries, "a deleveraging flush must fire"
    assert all(side == "LONG" for _, side in entries)
    assert all(i < N - 1 for i, _ in entries)


def test_oi_flush_reversal_shorts_when_price_rose_with_oi_flush():
    closes = [100.0] * (N - 20) + [100.0 * (1.01 ** k) for k in range(1, 21)]
    entries = make_oi_flush_reversal(_flush_tail())(_candles(closes),
                                                    PARAMS_CHANGE)
    assert entries
    assert all(side == "SHORT" for _, side in entries)


def test_oi_flush_reversal_quiet_oi_is_silent():
    closes = [100.0 * (0.999 ** i) for i in range(N)]
    entries = make_oi_flush_reversal(_flat_oi())(_candles(closes),
                                                 PARAMS_CHANGE)
    assert entries == []


def test_oi_build_momentum_follows_price_direction():
    oi = _flat_oi()
    for i in range(N - 20, N):
        oi[i] = oi[i - 1] * 1.03   # OI build-up
    closes = [100.0] * (N - 20) + [100.0 * (1.01 ** k) for k in range(1, 21)]
    entries = make_oi_build_momentum(oi)(_candles(closes), PARAMS_CHANGE)
    assert entries
    assert all(side == "LONG" for _, side in entries)


def test_toptrader_follow_longs_high_ratio_shorts_low():
    # 3-value wiggle: a discrete uniform's max |z| is sqrt(3/2) ~ 1.22, safely
    # inside the 1.5 threshold, so only the injected extremes fire.
    base = [1.0 + 0.0005 * (i % 3) for i in range(N)]
    high = base[:]
    for i in range(N - 10, N):
        high[i] = 2.5   # top traders heavily long
    entries = make_toptrader_follow(high)(_candles([100.0] * N), PARAMS_LEVEL)
    assert entries and all(side == "LONG" for _, side in entries)
    low = base[:]
    for i in range(N - 10, N):
        low[i] = 0.3    # top traders heavily short
    entries = make_toptrader_follow(low)(_candles([100.0] * N), PARAMS_LEVEL)
    assert entries and all(side == "SHORT" for _, side in entries)


def test_taker_flow_momentum_follows_aggressive_flow():
    flow = [1.0 + 0.0005 * (i % 3) for i in range(N)]
    for i in range(N - 10, N):
        flow[i] = 3.0   # aggressive taker buying
    entries = make_taker_flow_momentum(flow)(_candles([100.0] * N),
                                             PARAMS_LEVEL)
    assert entries and all(side == "LONG" for _, side in entries)


def test_generators_are_deterministic_and_skip_none_gaps():
    feature = _flush_tail()
    feature[50] = None
    gen = make_oi_flush_reversal(feature)
    closes = [100.0] * N
    assert gen(_candles(closes), PARAMS_CHANGE) == gen(_candles(closes),
                                                       PARAMS_CHANGE)


@pytest.mark.parametrize("family,params", [
    ("oi_flush_reversal", PARAMS_CHANGE),
    ("oi_build_momentum", PARAMS_CHANGE),
    ("toptrader_follow", PARAMS_LEVEL),
    ("taker_flow_momentum", PARAMS_LEVEL),
])
def test_generate_entries_routes_positioning_families(family, params):
    bundle = DataBundle(candles=_candles([100.0] * N), feature=_flat_oi())
    assert isinstance(generate_entries(family, params, bundle), list)


def test_generate_entries_requires_feature_for_positioning():
    bundle = DataBundle(candles=_candles([100.0] * N))
    with pytest.raises(ValueError, match="feature"):
        generate_entries("oi_flush_reversal", PARAMS_CHANGE, bundle)
