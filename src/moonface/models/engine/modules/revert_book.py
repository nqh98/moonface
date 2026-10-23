from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from moonface.core.indicators import sma
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.deriv import funding_points_ct, oi_flush_points
from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import ModuleScore, TfViews
from moonface.models.engine.modules.trend_book import TREND_MA

W_SWEEP = 20
W_RECLAIM = 15
W_DIVERGENCE = 25
W_FUND_CT = 15
W_OI_FLUSH = 10
W_STRETCH = 15

SWEEP_LOOKBACK = 20
EVENT_TTL_BARS = 3
PIVOT_K = 2
DIV_MAX_SPAN = 40
RSI_PERIOD = 14
OI_FLUSH_LOOKBACK = 12

_AR = "mean_revert"


@dataclass(frozen=True)
class SweepState:
    direction: int
    level: float
    wick_extreme: float
    sweep_index: int
    reclaim_index: int | None


@dataclass(frozen=True)
class _Pivot:
    index: int
    price: float
    rsi: float


def _score(module: str, direction: int, points: int, data_ok: bool,
           *evidence: str) -> ModuleScore:
    return ModuleScore(
        module=module,
        direction=direction,
        points=points,
        archetype=_AR,
        data_ok=data_ok,
        evidence=tuple(evidence),
    )


def _wilder_rsi_series(closes: list[float], period: int = RSI_PERIOD) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def _sweep_at(candles_1h: list[Candle], i: int,
              lookback: int) -> SweepState | None:
    if i < lookback:
        return None
    window = candles_1h[i - lookback:i]
    bar = candles_1h[i]
    prior_low = min(c.low for c in window)
    prior_high = max(c.high for c in window)
    long_sweep = bar.low < prior_low and bar.close > prior_low
    short_sweep = bar.high > prior_high and bar.close < prior_high
    if long_sweep and not short_sweep:
        return SweepState(1, prior_low, bar.low, i, None)
    if short_sweep and not long_sweep:
        return SweepState(-1, prior_high, bar.high, i, None)
    return None


def _reclaimed(state: SweepState, bar: Candle) -> bool:
    if state.direction > 0:
        return bar.close > state.level
    return bar.close < state.level


def sweep_state(candles_1h: list[Candle], lookback: int = SWEEP_LOOKBACK) -> SweepState | None:
    last = len(candles_1h) - 1
    if last < lookback:
        return None
    start = max(lookback, last - EVENT_TTL_BARS - 1)
    for i in range(last, start - 1, -1):
        state = _sweep_at(candles_1h, i, lookback)
        if state is None:
            continue
        if last == i:
            return state
        if i + 1 >= len(candles_1h) or not _reclaimed(state, candles_1h[i + 1]):
            continue
        age = last - (i + 1)
        if 0 <= age < EVENT_TTL_BARS:
            return SweepState(state.direction, state.level, state.wick_extreme,
                              state.sweep_index, i + 1)
    return None


def _sweep_score(h1: list[Candle]) -> ModuleScore:
    if len(h1) < SWEEP_LOOKBACK + 1:
        return _score("m1_sweep", 0, 0, False, "insufficient h1 history")
    state = sweep_state(h1, SWEEP_LOOKBACK)
    if state is None:
        return _score("m1_sweep", 0, 0, True, "no active sweep")
    return _score("m1_sweep", state.direction, W_SWEEP, True,
                  f"level={state.level:.4f}",
                  f"wick_extreme={state.wick_extreme:.4f}",
                  f"sweep_index={state.sweep_index}")


def _reclaim_score(h1: list[Candle]) -> ModuleScore:
    if len(h1) < SWEEP_LOOKBACK + 1:
        return _score("m2_reclaim", 0, 0, False, "insufficient h1 history")
    state = sweep_state(h1, SWEEP_LOOKBACK)
    if state is None or state.reclaim_index is None:
        return _score("m2_reclaim", 0, 0, True, "no active reclaim")
    return _score("m2_reclaim", state.direction, W_RECLAIM, True,
                  f"level={state.level:.4f}",
                  f"confirm_index={state.reclaim_index}",
                  f"wick_extreme={state.wick_extreme:.4f}")


def _pivot_indices(values: list[float], k: int, *, highs: bool) -> list[int]:
    out: list[int] = []
    for i in range(k, len(values) - k):
        cur = values[i]
        left = values[i - k:i]
        right = values[i + 1:i + k + 1]
        if highs:
            if all(cur > other for other in left) and all(cur >= other for other in right):
                out.append(i)
        else:
            if all(cur < other for other in left) and all(cur <= other for other in right):
                out.append(i)
    return out


def _latest_pivot_pair(candles: list[Candle], *, highs: bool) -> tuple[_Pivot, _Pivot] | None:
    closes = [c.close for c in candles]
    rsis = _wilder_rsi_series(closes)
    series = [c.high for c in candles] if highs else [c.low for c in candles]
    indices = _pivot_indices(series, PIVOT_K, highs=highs)
    pivots: list[_Pivot] = []
    for i in indices:
        value = rsis[i]
        if value is None:
            continue
        pivots.append(_Pivot(i, series[i], value))
    if len(pivots) < 2:
        return None
    return pivots[-2], pivots[-1]


def _divergence_score(h1: list[Candle]) -> ModuleScore:
    need = RSI_PERIOD + 1 + 2 * PIVOT_K
    if len(h1) < need:
        return _score("m3_divergence", 0, 0, False, "insufficient h1 history")

    low_pair = _latest_pivot_pair(h1, highs=False)
    if low_pair is not None:
        first, second = low_pair
        span = second.index - first.index
        if span <= DIV_MAX_SPAN and second.price < first.price and second.rsi > first.rsi:
            return _score("m3_divergence", 1, W_DIVERGENCE, True,
                          f"price={first.price:.4f}->{second.price:.4f}",
                          f"rsi={first.rsi:.4f}->{second.rsi:.4f}",
                          f"span={span}")

    high_pair = _latest_pivot_pair(h1, highs=True)
    if high_pair is not None:
        first, second = high_pair
        span = second.index - first.index
        if span <= DIV_MAX_SPAN and second.price > first.price and second.rsi < first.rsi:
            return _score("m3_divergence", -1, W_DIVERGENCE, True,
                          f"price={first.price:.4f}->{second.price:.4f}",
                          f"rsi={first.rsi:.4f}->{second.rsi:.4f}",
                          f"span={span}")

    return _score("m3_divergence", 0, 0, True, "no confirmed divergence")


def _funding_countertrend_score(deriv: Any | None,
                                macro: MacroState) -> ModuleScore:
    if deriv is None or all(getattr(deriv, name, None) is None
                            for name in ("funding_pct", "funding_rate")):
        return _score("m4_fund_ct", 0, 0, False, "funding unavailable")
    long_points, long_evidence = funding_points_ct(deriv, 1)
    short_points, short_evidence = funding_points_ct(deriv, -1)
    if long_points > short_points:
        return _score("m4_fund_ct", 1, long_points, True,
                      long_evidence, f"macro={macro.effective()}")
    if short_points > long_points:
        return _score("m4_fund_ct", -1, short_points, True,
                      short_evidence, f"macro={macro.effective()}")
    return _score("m4_fund_ct", 0, 0, True,
                  long_evidence, f"macro={macro.effective()}")


def _oi_flush_score(h1: list[Candle], deriv: Any | None) -> ModuleScore:
    if len(h1) < OI_FLUSH_LOOKBACK + 1:
        return _score("m5_oi_flush", 0, 0, False, "insufficient h1 history")
    if deriv is None or all(getattr(deriv, name, None) is None
                            for name in ("oi_change_6h", "oi_change_pct", "oi_change_z")):
        return _score("m5_oi_flush", 0, 0, False, "oi unavailable")
    points, evidence = oi_flush_points(deriv)
    if points == 0:
        return _score("m5_oi_flush", 0, 0, True, evidence)
    past = h1[-1 - OI_FLUSH_LOOKBACK].close
    if past == 0:
        return _score("m5_oi_flush", 0, 0, False, "zero past close")
    move = h1[-1].close / past - 1.0
    if move == 0:
        return _score("m5_oi_flush", 0, 0, True, evidence, "flat price")
    direction = 1 if move < 0 else -1
    return _score("m5_oi_flush", direction, points, True,
                  evidence, f"price_move={move:.4%}")


def _stretch_score(h1: list[Candle], cfg: EngineConfig) -> ModuleScore:
    need = max(TREND_MA, cfg.atr_period)
    if len(h1) < need:
        return _score("m6_stretch", 0, 0, False, "insufficient h1 history")
    closes = [c.close for c in h1]
    mean = sma(closes, TREND_MA)
    a = atr(h1, cfg.atr_period)
    if a <= 0:
        return _score("m6_stretch", 0, 0, False, "zero atr")
    z = (closes[-1] - mean) / a
    if z <= -2.0:
        return _score("m6_stretch", 1, W_STRETCH, True,
                      f"sma={mean:.4f}", f"atr={a:.4f}", f"stretch={z:.4f}")
    if z >= 2.0:
        return _score("m6_stretch", -1, W_STRETCH, True,
                      f"sma={mean:.4f}", f"atr={a:.4f}", f"stretch={z:.4f}")
    return _score("m6_stretch", 0, 0, True,
                  f"sma={mean:.4f}", f"atr={a:.4f}", f"stretch={z:.4f}")


def score(views: TfViews, macro: MacroState, deriv: Any | None,
          cfg: EngineConfig) -> list[ModuleScore]:
    return [
        _sweep_score(views.h1),
        _reclaim_score(views.h1),
        _divergence_score(views.h1),
        _funding_countertrend_score(deriv, macro),
        _oi_flush_score(views.h1, deriv),
        _stretch_score(views.h1, cfg),
    ]
