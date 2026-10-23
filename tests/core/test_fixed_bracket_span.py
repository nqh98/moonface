# tests/foundation/test_fixed_bracket_span.py
from moonface.core.metrics import resolve_trade_span, single_trade_r
from moonface.data.ohlcv import Candle  # adjust import if Candle lives elsewhere


def _ramp(n: int, start: float = 100.0, step: float = 1.0) -> list[Candle]:
    out = []
    for k in range(n):
        c = start + step * k
        out.append(Candle(timestamp_ms=k * 14_400_000, open=c, high=c + 2.0,
                           low=c - 2.0, close=c, volume=1.0))
    return out


def test_fixed_bracket_span_net_r_matches_single_trade_r():
    candles = _ramp(120)
    params = {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}
    i, side = 20, "LONG"
    span = resolve_trade_span(candles, i, side, "fixed_bracket", params)
    base = single_trade_r(candles, i, side, "fixed_bracket", params)
    assert span is not None and base is not None
    entry_idx, exit_idx, net_r, atr_frac = span
    assert entry_idx == i
    assert exit_idx > i
    assert net_r == base[0]          # net R identical
    assert atr_frac == base[1]       # atr_frac identical


def test_fixed_bracket_span_short_side():
    candles = _ramp(120)
    params = {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}
    span = resolve_trade_span(candles, 20, "SHORT", "fixed_bracket", params)
    base = single_trade_r(candles, 20, "SHORT", "fixed_bracket", params)
    assert span is not None and base is not None
    assert span[2] == base[0]
