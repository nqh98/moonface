from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from moonface.data.series import fetch_metrics_history
from moonface.research.universe_data import fetch_funding_rates
from moonface.models.engine.deriv import (
    FUND_WINDOW_DAYS,
    DerivSnapshot,
    _oi_change_from_points,
    _percentile_of_last,
)

_DAY_MS = 86_400_000
_HOUR_MS = 3_600_000
_OI_FETCH_WINDOW_H = 8
_OI_FIELD = "sum_open_interest"

Point = tuple[int, float]


@dataclass(frozen=True)
class DerivCoverage:
    scored_bars: int
    funding_ok: int
    oi_ok: int

    def funding_fraction(self) -> float:
        if self.scored_bars == 0:
            return 0.0
        return self.funding_ok / self.scored_bars

    def oi_fraction(self) -> float:
        if self.scored_bars == 0:
            return 0.0
        return self.oi_ok / self.scored_bars


def _normalise_points(points: Iterable[tuple[int, Any]]) -> list[Point]:
    out: list[Point] = []
    for ts, value in points:
        out.append((int(ts), float(value)))
    return sorted(out)


def _normalise_oi_points(points: Iterable[tuple[int, Any]]) -> list[Point]:
    out: list[Point] = []
    for ts, value in points:
        if isinstance(value, dict):
            raw = value.get(_OI_FIELD)
            if raw is None:
                continue
            value = raw
        out.append((int(ts), float(value)))
    return sorted(out)


def _slice_points(points: Sequence[Point], timestamps: Sequence[int],
                  start_ms: int, end_ms: int) -> list[Point]:
    lo = bisect_left(timestamps, start_ms)
    hi = bisect_right(timestamps, end_ms)
    return list(points[lo:hi])


def build_deriv_by_index(
    candles,
    warmup: int,
    archive_symbol: str,
    cache_dir: str,
    funding_points: Iterable[tuple[int, Any]] | None = None,
    oi_points: Iterable[tuple[int, Any]] | None = None,
) -> tuple[dict[int, DerivSnapshot], DerivCoverage]:
    scored_start = max(0, warmup)
    scored_indices = range(scored_start, len(candles))
    scored_bars = max(0, len(candles) - scored_start)
    if scored_bars == 0:
        return {}, DerivCoverage(scored_bars=0, funding_ok=0, oi_ok=0)

    first_now_ms = int(candles[scored_start].timestamp_ms) + _HOUR_MS
    last_now_ms = int(candles[-1].timestamp_ms) + _HOUR_MS

    if funding_points is None:
        funding_points = fetch_funding_rates(
            archive_symbol,
            first_now_ms - FUND_WINDOW_DAYS * _DAY_MS,
            last_now_ms + 1,
            cache_dir,
        )
    if oi_points is None:
        oi_points = fetch_metrics_history(
            archive_symbol,
            first_now_ms - _OI_FETCH_WINDOW_H * _HOUR_MS,
            last_now_ms + 1,
            cache_dir,
        )

    funding = _normalise_points(funding_points)
    oi = _normalise_oi_points(oi_points)
    funding_ts = [ts for ts, _ in funding]
    oi_ts = [ts for ts, _ in oi]

    deriv_by_index: dict[int, DerivSnapshot] = {}
    funding_ok = 0
    oi_ok = 0
    for j in scored_indices:
        now_ms = int(candles[j].timestamp_ms) + _HOUR_MS
        funding_window = _slice_points(
            funding,
            funding_ts,
            now_ms - FUND_WINDOW_DAYS * _DAY_MS,
            now_ms,
        )
        oi_window = _slice_points(
            oi,
            oi_ts,
            now_ms - _OI_FETCH_WINDOW_H * _HOUR_MS,
            now_ms,
        )
        funding_pct = _percentile_of_last(funding_window)
        oi_change_6h = _oi_change_from_points(oi_window)
        if funding_pct is not None:
            funding_ok += 1
        if oi_change_6h is not None:
            oi_ok += 1
        deriv_by_index[j] = DerivSnapshot(
            funding_pct=funding_pct,
            oi_change_6h=oi_change_6h,
        )

    coverage = DerivCoverage(
        scored_bars=scored_bars,
        funding_ok=funding_ok,
        oi_ok=oi_ok,
    )
    return deriv_by_index, coverage
