"""Order-book imbalance hypothesis family over the Binance Vision bookDepth
archive (±1% band bid/ask notional).

Pre-registered mechanism, one direction (follow): resting depth imbalance is
informed pressure, so strong bid-side imbalance predicts positive forward
drift and strong ask-side imbalance predicts negative forward drift. The
signal is symmetric by construction. No exits, stops, TPs, or grids are fit
here — this is a mechanism generator only.

The generator sees candles plus one aligned per-bar imbalance series (the mean
of the ~30s snapshots inside each bar). It reuses the positioning family's
rolling-window z-score follow shape so the magnitude test is identical across
studies."""
from __future__ import annotations

from statistics import fmean

from moonface.research.edge.positioning_signals import _make_level_follow
from moonface.core.models import Candle

Entry = tuple[int, str]


def bar_mean_imbalance(candles: list[Candle],
                       points: list[tuple[int, float]]) -> list[float | None]:
    """Per-bar mean imbalance aligned 1:1 with candles. Each bar spans
    [candle.timestamp_ms, next candle's timestamp_ms); the last bar uses the
    same width as the previous one. A bar with no snapshots is None.

    No lookahead: snapshot ts must fall within the bar's own half-open window,
    and the bar's forward return is only ever scored from its close onward."""
    if not candles:
        return []
    width = (candles[1].timestamp_ms - candles[0].timestamp_ms
             if len(candles) > 1 else 0)
    pts = sorted(points)
    series: list[float | None] = []
    j = 0
    for idx, c in enumerate(candles):
        start = c.timestamp_ms
        end = (candles[idx + 1].timestamp_ms if idx + 1 < len(candles)
               else start + width)
        while j < len(pts) and pts[j][0] < start:
            j += 1
        bucket = []
        k = j
        while k < len(pts) and pts[k][0] < end:
            bucket.append(pts[k][1])
            k += 1
        series.append(fmean(bucket) if bucket else None)
    return series


def make_ob_imbalance_follow(feature: list[float | None]):
    """Follow resting ±1% depth imbalance at rolling-window extremes:
    z >= z_thr -> LONG, z <= -z_thr -> SHORT (symmetric)."""
    return _make_level_follow(feature)
