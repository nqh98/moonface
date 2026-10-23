import random

from moonface.core.exits import (atr_trail, horizon_hold, horizon_wide_stop,
                                       _SPAN_FNS)
from moonface.core.metrics import resolve_trade_span, single_trade_r
from moonface.core.models import Candle


def _candles(prices, seed=0):
    rnd = random.Random(seed)
    return [Candle(timestamp_ms=t * 3_600_000, open=p, high=p * 1.01,
                   low=p * 0.99, close=p, volume=1.0 + rnd.random())
            for t, p in enumerate(prices)]


def test_span_registry_has_four_exits():
    assert set(_SPAN_FNS) == {"horizon_hold", "atr_trail",
                              "horizon_wide_stop", "fixed_bracket"}


def test_span_gross_matches_exit_fn_gross():
    prices = [100.0 + i + 5 * ((-1) ** i) for i in range(200)]
    candles = _candles(prices)
    cases = [
        ("horizon_hold", {"n_bars": 24, "atr_period": 14}),
        ("atr_trail", {"k_trail": 2.0, "max_bars": 48, "atr_period": 14}),
        ("horizon_wide_stop", {"n_bars": 24, "k_stop": 2.5, "atr_period": 14}),
    ]
    for exit_name, params in cases:
        for i in (10, 30, 60, 100):
            span = _SPAN_FNS[exit_name](i, "LONG", candles, params)
            gross_fn = {"horizon_hold": horizon_hold, "atr_trail": atr_trail,
                        "horizon_wide_stop": horizon_wide_stop}[exit_name](
                i, "LONG", candles, params)
            if gross_fn is None:
                assert span is None
                continue
            assert span is not None
            exit_idx, gross_span = span
            assert gross_span == gross_fn
            assert exit_idx > i


def test_horizon_hold_span_exit_idx():
    prices = [100.0 + i for i in range(200)]
    candles = _candles(prices)
    exit_idx, _ = _SPAN_FNS["horizon_hold"](10, "LONG", candles,
                                            {"n_bars": 24, "atr_period": 14})
    assert exit_idx == 10 + 24


def test_resolve_trade_span_matches_single_trade_r():
    prices = [100.0 + i + 5 * ((-1) ** i) for i in range(200)]
    candles = _candles(prices)
    for exit_name, params in [
        ("atr_trail", {"k_trail": 2.0, "max_bars": 48, "atr_period": 14}),
        ("horizon_wide_stop",
         {"n_bars": 24, "k_stop": 2.5, "atr_period": 14}),
    ]:
        for i in (10, 50, 90):
            tr = single_trade_r(candles, i, "LONG", exit_name, params)
            span = resolve_trade_span(candles, i, "LONG", exit_name, params)
            if tr is None:
                assert span is None
                continue
            assert span is not None
            entry_idx, exit_idx, net_r, atr_frac = span
            assert entry_idx == i
            assert (net_r, atr_frac) == tr
