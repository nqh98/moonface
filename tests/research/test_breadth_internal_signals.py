from moonface.core.models import Candle
from moonface.research.breadth_internal.signals import (
    btc_daily_closes,
    breadth_divergence_state,
    _extreme_flags,
    dispersion_regime_state,
    dispersion_series,
    net_new_highs_series,
    net_new_highs_state,
)
from moonface.research.universe_data import DailyRow


DAY_MS = 86_400_000
H4_MS = 4 * 3_600_000


def _btc(closes: list[float]) -> list[Candle]:
    return [
        Candle(i * H4_MS, c - 1.0, c + 1.0, c - 2.0, c, 1.0)
        for i, c in enumerate(closes)
    ]


def _btc_daily(closes: list[float]) -> list[Candle]:
    return [
        Candle(i * DAY_MS, c - 1.0, c + 1.0, c - 2.0, c, 1.0)
        for i, c in enumerate(closes)
    ]


def _rows(closes: list[float], start: int = 0) -> list[DailyRow]:
    return [
        DailyRow(start + i * DAY_MS, close, 1.0)
        for i, close in enumerate(closes)
    ]


def _rows_at(closes: list[float], timestamps: list[int]) -> list[DailyRow]:
    return [
        DailyRow(ts, close, 1.0)
        for ts, close in zip(timestamps, closes, strict=True)
    ]


def test_btc_daily_closes_samples_last_4h_at_or_before_day() -> None:
    btc = _btc([100.0, 101.0, 102.0, 103.0, 104.0])
    out = btc_daily_closes(btc, [8 * 3_600_000, 12 * 3_600_000, 13 * 3_600_000])
    assert out == {
        8 * 3_600_000: 102.0,
        12 * 3_600_000: 103.0,
        13 * 3_600_000: 103.0,
    }


def test_net_new_highs_series_counts_highs_minus_lows() -> None:
    daily = {
        "AAA": _rows([10.0, 11.0, 12.0]),
        "BBB": _rows([10.0, 9.0, 8.0]),
        "BTCUSDT": _rows([1.0, 99.0, 100.0]),
    }
    assert net_new_highs_series(daily, n=2) == [
        (DAY_MS, 0.0),
        (2 * DAY_MS, 0.0),
    ]


def test_extreme_flags_use_inclusive_trailing_window() -> None:
    rows = _rows([10.0, 11.0, 9.0])
    assert _extreme_flags(rows, 2, "high") == {
        DAY_MS: True,
        2 * DAY_MS: False,
    }
    assert _extreme_flags(rows, 2, "low") == {
        DAY_MS: False,
        2 * DAY_MS: True,
    }


def test_net_new_highs_state_long_on_broad_highs() -> None:
    daily = {
        "AAA": _rows([10.0, 11.0, 12.0]),
        "BBB": _rows([10.0, 11.0, 12.0]),
    }
    assert net_new_highs_state(daily, n=2, long_thr=0.5, short_thr=-0.5) == [
        (DAY_MS, "LONG"),
        (2 * DAY_MS, "LONG"),
    ]


def test_divergence_short_when_price_up_breadth_down() -> None:
    daily = {
        "AAA": _rows_at([10.0, 12.0, 8.0], [0, DAY_MS, 3 * DAY_MS]),
        "BBB": _rows_at([10.0, 8.0, 7.0], [0, DAY_MS, 3 * DAY_MS]),
        "BTCUSDT": _rows([1.0, 100.0, 101.0, 102.0]),
    }
    btc = _btc_daily([100.0, 110.0, 105.0, 120.0])
    assert breadth_divergence_state(daily, btc, n=1, base_period=2) == [
        (DAY_MS, "FLAT"),
        (3 * DAY_MS, "SHORT"),
    ]


def test_divergence_state_returns_empty_for_nonpositive_lag() -> None:
    daily = {
        "AAA": _rows([10.0, 12.0, 8.0]),
        "BBB": _rows([10.0, 8.0, 7.0]),
        "BTCUSDT": _rows([1.0, 100.0, 101.0]),
    }
    btc = _btc_daily([100.0, 110.0, 105.0])
    assert breadth_divergence_state(daily, btc, n=0, base_period=2) == []


def test_dispersion_series_uses_cross_sectional_return_spread() -> None:
    daily = {
        "AAA": _rows([100.0, 100.0, 100.0]),
        "BBB": _rows([100.0, 150.0]),
        "CCC": _rows([100.0, 200.0]),
        "BTCUSDT": _rows([1.0, 100.0, 101.0]),
    }
    assert dispersion_series(daily, d=1) == [
        (DAY_MS, 0.5),
    ]


def test_dispersion_regime_follows_dispersion_gate_and_btc_ma() -> None:
    daily = {
        "AAA": _rows([100.0, 100.0, 100.0, 100.0]),
        "BBB": _rows([100.0, 150.0, 300.0, 750.0]),
        "CCC": _rows([100.0, 200.0, 600.0, 2400.0]),
        "BTCUSDT": _rows([1.0, 100.0, 101.0, 102.0]),
    }
    btc = [
        Candle(DAY_MS, 99.0, 101.0, 98.0, 100.0, 1.0),
        Candle(2 * DAY_MS, 199.0, 201.0, 198.0, 200.0, 1.0),
        Candle(3 * DAY_MS, 249.0, 251.0, 248.0, 250.0, 1.0),
    ]
    assert dispersion_regime_state(daily, btc, d=1, m_ma=2, window=2, p=0.0) == [
        (DAY_MS, "FLAT"),
        (2 * DAY_MS, "FLAT"),
        (3 * DAY_MS, "LONG"),
    ]
