from dataclasses import dataclass

from moonface.research.donchian_filter.adx import adx_series


@dataclass
class C:
    high: float
    low: float
    close: float
    timestamp_ms: int = 0
    open: float = 0.0


def _trend(n):
    out = []
    for i in range(n):
        base = 100.0 + i
        out.append(C(high=base + 0.5, low=base - 0.5, close=base + 0.3))
    return out


def _chop(n):
    out = []
    for i in range(n):
        hi, lo = (101.0, 99.0) if i % 2 == 0 else (101.2, 99.2)
        out.append(C(high=hi, low=lo, close=(hi + lo) / 2))
    return out


def test_warmup_is_zero():
    adx = adx_series(_trend(60), period=14)
    assert all(v == 0.0 for v in adx[: 2 * 14 - 1])
    assert adx[2 * 14 - 1] > 0.0


def test_trend_has_high_adx():
    adx = adx_series(_trend(120), period=14)
    assert adx[-1] > 40.0


def test_chop_has_low_adx():
    adx = adx_series(_chop(120), period=14)
    assert adx[-1] < 20.0


def test_causal_no_lookahead():
    full = _trend(80)
    k = 50
    assert adx_series(full, 14)[k] == adx_series(full[: k + 1], 14)[k]
