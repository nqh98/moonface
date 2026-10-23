from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.breadth.signals import (
    DAY_MS,
    breadth_momentum_series,
    entries_from_state,
    ma_above_flags,
    level_state,
    pct_above_ma_series,
    positive_return_flags,
    thrust_state,
)
from moonface.research.universe_data import DailyRow

_D = DAY_MS


def _rows(closes: list[float], start: int = 0) -> list[DailyRow]:
    return [
        DailyRow(ts_ms=start + i * _D, close=c, quote_volume=1.0)
        for i, c in enumerate(closes)
    ]


def test_ma_above_flags_uses_only_trailing_closes() -> None:
    flags = ma_above_flags(_rows([10, 12, 8]), period=2)
    assert flags == {_D: True, 2 * _D: False}


def test_positive_return_flags() -> None:
    flags = positive_return_flags(_rows([10, 11, 9]), days=1)
    assert flags == {_D: True, 2 * _D: False}


def test_pct_above_ma_excludes_btc_and_averages_membership() -> None:
    daily = {
        "AAA": _rows([10, 12]),
        "BBB": _rows([10, 8]),
        "BTCUSDT": _rows([1, 100]),
    }
    series = pct_above_ma_series(daily, period=2)
    assert series == [(_D, 0.5)]


def test_breadth_momentum_series_fraction() -> None:
    daily = {"AAA": _rows([10, 11]), "BBB": _rows([10, 9])}
    assert breadth_momentum_series(daily, days=1) == [(_D, 0.5)]


def test_level_state_bands() -> None:
    series = [(0, 0.60), (1, 0.50), (2, 0.40)]
    assert level_state(series, long_thr=0.55, short_thr=0.45) == [
        (0, "LONG"),
        (1, "FLAT"),
        (2, "SHORT"),
    ]


def test_thrust_state_up_then_down_holds_between() -> None:
    series = [(0, 0.50), (1, 0.30), (2, 0.70), (3, 0.65), (4, 0.30)]
    assert thrust_state(series, low_band=0.40, high_band=0.60, window=2) == [
        (0, "FLAT"),
        (1, "FLAT"),
        (2, "LONG"),
        (3, "LONG"),
        (4, "SHORT"),
    ]


_H = 3_600_000


def _btc(n: int, start: int = 0, step: int = 4 * _H) -> list[Candle]:
    return [
        Candle(start + i * step, 100.0, 100.0, 100.0, 100.0, 1.0)
        for i in range(n)
    ]


def test_entries_align_as_of_next_day_and_dedup() -> None:
    btc = _btc(40)
    state = [(0, "LONG"), (DAY_MS, "LONG"), (2 * DAY_MS, "SHORT")]
    entries = entries_from_state(btc, state, h=48)
    assert entries == [(6, "LONG")]


def test_entries_no_dedup_when_spaced_beyond_h() -> None:
    btc = _btc(40)
    state = [(0, "LONG"), (DAY_MS, "SHORT")]
    assert entries_from_state(btc, state, h=3) == [(6, "LONG"), (12, "SHORT")]
