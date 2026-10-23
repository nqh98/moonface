import pytest

from moonface.core.models import Candle
from moonface.models.engine.deriv import _percentile_of_last
from moonface.models.engine.deriv_history import build_deriv_by_index


HOUR_MS = 3_600_000
DAY_MS = 86_400_000
FIVE_MIN_MS = 300_000


def _candle(ts_ms: int) -> Candle:
    return Candle(ts_ms, 100.0, 101.0, 99.0, 100.5, 10.0)


def test_funding_percentile_matches_live_semantics():
    now_ms = 12 * HOUR_MS
    candles = [_candle(now_ms - HOUR_MS)]
    funding_points = [
        (now_ms - 24 * HOUR_MS, 0.001),
        (now_ms - 16 * HOUR_MS, -0.002),
        (now_ms - 8 * HOUR_MS, 0.003),
        (now_ms, 0.002),
    ]

    deriv_by_index, coverage = build_deriv_by_index(
        candles, warmup=0, archive_symbol="BTCUSDT", cache_dir="/unused",
        funding_points=funding_points, oi_points=[],
    )

    assert deriv_by_index[0].funding_pct == _percentile_of_last(funding_points)
    assert coverage.scored_bars == 1
    assert coverage.funding_ok == 1
    assert coverage.oi_ok == 0
    assert coverage.funding_fraction() == 1.0
    assert coverage.oi_fraction() == 0.0


def test_point_after_close_is_excluded_from_funding_percentile():
    now_ms = HOUR_MS
    candles = [_candle(0)]
    funding_points = [
        (0, 0.001),
        (now_ms, 0.002),
        (now_ms + 1, -0.999),
    ]

    deriv_by_index, _ = build_deriv_by_index(
        candles, warmup=0, archive_symbol="BTCUSDT", cache_dir="/unused",
        funding_points=funding_points, oi_points=[],
    )

    assert deriv_by_index[0].funding_pct == 100.0


def test_funding_window_is_thirty_days_inclusive():
    now_ms = 40 * DAY_MS
    candles = [_candle(now_ms - HOUR_MS)]
    funding_points = [
        (now_ms - 30 * DAY_MS - 1, 100.0),
        (now_ms - 30 * DAY_MS, 2.0),
        (now_ms, 1.0),
    ]

    deriv_by_index, _ = build_deriv_by_index(
        candles, warmup=0, archive_symbol="BTCUSDT", cache_dir="/unused",
        funding_points=funding_points, oi_points=[],
    )

    assert deriv_by_index[0].funding_pct == 50.0


def test_oi_change_from_five_min_points_is_computed_correctly():
    now_ms = 11 * HOUR_MS
    candles = [_candle(now_ms - HOUR_MS)]
    oi_points = [
        (ts, 100.0 + 25.0 * (ts - (now_ms - 6 * HOUR_MS)) / (6 * HOUR_MS))
        for ts in range(now_ms - 6 * HOUR_MS, now_ms + FIVE_MIN_MS, FIVE_MIN_MS)
    ]

    deriv_by_index, coverage = build_deriv_by_index(
        candles, warmup=0, archive_symbol="BTCUSDT", cache_dir="/unused",
        funding_points=[], oi_points=oi_points,
    )

    assert deriv_by_index[0].oi_change_6h == pytest.approx(0.25)
    assert coverage.oi_ok == 1


def test_coverage_counts_scored_bars_only():
    candles = [_candle(i * HOUR_MS) for i in range(5)]
    funding_points = [(i * HOUR_MS, float(i)) for i in range(1, 6)]
    oi_points = [
        (ts, 100.0 + ts / HOUR_MS)
        for ts in range(-3 * HOUR_MS, 6 * HOUR_MS, FIVE_MIN_MS)
    ]

    deriv_by_index, coverage = build_deriv_by_index(
        candles, warmup=2, archive_symbol="BTCUSDT", cache_dir="/unused",
        funding_points=funding_points, oi_points=oi_points,
    )

    assert sorted(deriv_by_index) == [2, 3, 4]
    assert coverage.scored_bars == 3
    assert coverage.funding_ok == 3
    assert coverage.oi_ok == 3
    assert coverage.funding_fraction() == 1.0
    assert coverage.oi_fraction() == 1.0
