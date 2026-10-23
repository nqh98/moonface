"""Positioning hypothesis family over Binance futures metrics (open interest,
top-trader long/short ratio, taker buy/sell volume ratio).

Pre-registered mechanisms, one direction each — chosen from the mechanism, not
from the data:
- oi_flush_reversal: a violent open-interest drop is forced deleveraging;
  liquidation cascades overshoot, so fade the concurrent price move.
- oi_build_momentum: rising open interest while price moves means new money
  joining the move, not shorts covering — follow it.
- toptrader_follow: the venue's top-trader cohort is its documented
  smart-money sample — follow their net positioning at window extremes.
- taker_flow_momentum: aggressive (taker) volume imbalance is informed urgency
  — follow it at window extremes.

The generators only see candles plus one aligned feature series; the loader
enforces coverage, so they only have to be deterministic and gap-tolerant."""
from __future__ import annotations

from statistics import fmean, pstdev

from moonface.core.models import Candle

Entry = tuple[int, str]
FeatureSeries = list  # float | None, aligned 1:1 with candles


def _changes(feature: FeatureSeries, lookback: int,
             n: int) -> list[float | None]:
    rets: list[float | None] = [None] * n
    for i in range(lookback, min(n, len(feature))):
        now, then = feature[i], feature[i - lookback]
        if now is not None and then is not None and then != 0:
            rets[i] = now / then - 1.0
    return rets


def _zscore(series: list, i: int, window: int) -> float | None:
    x = series[i]
    if x is None:
        return None
    sample = [v for v in series[i - window + 1: i + 1] if v is not None]
    if len(sample) < window // 2:
        return None
    sd = pstdev(sample)
    if sd == 0:
        return None
    return (x - fmean(sample)) / sd


def _make_oi_change_family(feature: FeatureSeries, flush: bool):
    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        window, lookback = params["window"], params["lookback"]
        z_thr = params["z_thr"]
        n = len(candles)
        rets = _changes(feature, lookback, n)
        out: list[Entry] = []
        for i in range(window + lookback, n - 1):
            z = _zscore(rets, i, window)
            if z is None:
                continue
            if flush and z > -z_thr:
                continue
            if not flush and z < z_thr:
                continue
            past = candles[i - lookback].close
            if past == 0:
                continue
            price_ret = candles[i].close / past - 1.0
            if price_ret == 0:
                continue
            if flush:
                out.append((i, "LONG" if price_ret < 0 else "SHORT"))
            else:
                out.append((i, "LONG" if price_ret > 0 else "SHORT"))
        return out

    return gen


def make_oi_flush_reversal(feature: FeatureSeries):
    """OI-change z <= -z_thr (deleveraging flush): fade the price move."""
    return _make_oi_change_family(feature, flush=True)


def make_oi_build_momentum(feature: FeatureSeries):
    """OI-change z >= z_thr (new positioning): follow the price move."""
    return _make_oi_change_family(feature, flush=False)


def _make_level_follow(feature: FeatureSeries):
    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        window, z_thr = params["window"], params["z_thr"]
        n = len(candles)
        levels = [feature[i] if i < len(feature) else None for i in range(n)]
        out: list[Entry] = []
        for i in range(window, n - 1):
            z = _zscore(levels, i, window)
            if z is None:
                continue
            if z >= z_thr:
                out.append((i, "LONG"))
            elif z <= -z_thr:
                out.append((i, "SHORT"))
        return out

    return gen


def make_toptrader_follow(feature: FeatureSeries):
    """Follow top-trader net positioning at rolling-window extremes."""
    return _make_level_follow(feature)


def make_taker_flow_momentum(feature: FeatureSeries):
    """Follow aggressive taker-volume imbalance at rolling-window extremes."""
    return _make_level_follow(feature)
