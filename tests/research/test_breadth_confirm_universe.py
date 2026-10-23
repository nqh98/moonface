from moonface.research.universe_data import DailyRow
from moonface.research.xsection import build_universe
from moonface.research.breadth_confirm.universe_slice import (
    build_universe_slice,
    slice_membership_fn,
)

_DAY = 86_400_000


def _rows(vol, start=0, n=400, close=100.0):
    # n daily rows ending well after any asof we query; constant volume `vol`.
    return [DailyRow(ts_ms=start + i * _DAY, close=close, quote_volume=vol) for i in range(n)]


def _universe():
    # Five symbols with strictly ordered volumes: A>B>C>D>E.
    return {
        "AUSDT": _rows(50.0),
        "BUSDT": _rows(40.0),
        "CUSDT": _rows(30.0),
        "DUSDT": _rows(20.0),
        "EUSDT": _rows(10.0),
    }


def test_slice_returns_exact_rank_window():
    daily = _universe()
    asof = 300 * _DAY
    assert build_universe_slice(daily, asof, 0, 2, 30, 5) == ["AUSDT", "BUSDT"]
    assert build_universe_slice(daily, asof, 2, 4, 30, 5) == ["CUSDT", "DUSDT"]
    assert build_universe_slice(daily, asof, 4, 6, 30, 5) == ["EUSDT"]  # clamps past the end


def test_disjoint_windows_are_disjoint():
    daily = _universe()
    asof = 300 * _DAY
    primary = set(build_universe_slice(daily, asof, 0, 2, 30, 5))
    secondary = set(build_universe_slice(daily, asof, 2, 4, 30, 5))
    assert primary & secondary == set()


def test_top_slice_equals_build_universe():
    # Discovery reproduction guarantee: (0, N) slice == xsection.build_universe top_n=N.
    daily = _universe()
    asof = 300 * _DAY
    assert build_universe_slice(daily, asof, 0, 3, 30, 5) == build_universe(daily, asof, 3, 30, 5)


def test_history_floor_excludes_young_symbols():
    daily = _universe()
    daily["YOUNGUSDT"] = _rows(999.0, start=290 * _DAY, n=20)  # listed only 20d before asof
    asof = 300 * _DAY
    members = build_universe_slice(daily, asof, 0, 6, min_history_days=60, vol_days=5)
    assert "YOUNGUSDT" not in members  # fails the 60d listing-age floor despite top volume


def test_membership_is_point_in_time_and_cached():
    daily = _universe()
    is_member = slice_membership_fn(daily, 0, 2, 30, 5, rebalance_days=30)
    asof = 300 * _DAY
    assert is_member("AUSDT", asof) is True
    assert is_member("CUSDT", asof) is False
