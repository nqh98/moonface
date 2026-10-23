from __future__ import annotations

from moonface.core.metrics import COST_FRACTION, resolve_trade_span
from moonface.research.entries import PRICE_FAMILIES
from moonface.features.oi_features import nonoverlap
from moonface.research.regime_overlay.regime import regime_at
from moonface.research.regime_selector.grid import (MR_EXIT, MR_EXIT_PARAMS,
                                                    MR_FAMILY, MR_H, MR_PARAMS,
                                                    TREND_EXIT,
                                                    TREND_EXIT_PARAMS,
                                                    TREND_FAMILY, TREND_H,
                                                    TREND_PARAMS)


def _charge(net_r: float, atr_frac: float, cost_mult: float) -> float:
    if cost_mult == 1.0 or atr_frac <= 0:
        return net_r
    return net_r - (cost_mult - 1.0) * COST_FRACTION / atr_frac


def _leg_spans(candles, family, params, h, exit_name, exit_params):
    """[(entry_i, exit_ts, net_r, atr_frac)] for each nonoverlapping event."""
    events = nonoverlap(PRICE_FAMILIES[family](candles, params), h)
    out = []
    for i, side in events:
        span = resolve_trade_span(candles, i, side, exit_name, exit_params)
        if span is not None:
            _, exit_idx, net_r, atr_frac = span
            out.append((i, candles[exit_idx].timestamp_ms, net_r, atr_frac))
    return out


def _trend_legs(candles):
    return _leg_spans(candles, TREND_FAMILY, TREND_PARAMS, TREND_H,
                      TREND_EXIT, TREND_EXIT_PARAMS)


def _mr_legs(candles):
    return _leg_spans(candles, MR_FAMILY, MR_PARAMS, MR_H, MR_EXIT, MR_EXIT_PARAMS)


def _take(legs, candles, regime_def, macro, want, cost_mult):
    out = []
    for i, exit_ts, net_r, atr_frac in legs:
        if regime_at(candles[i].timestamp_ms, regime_def, macro) == want:
            out.append((exit_ts, _charge(net_r, atr_frac, cost_mult)))
    return out


def selector_rt(candles, macro, regime_def, riskoff_action, cost_mult=1.0):
    rt = _take(_trend_legs(candles), candles, regime_def, macro,
               "risk_on", cost_mult)
    if riskoff_action == "switch":
        rt += _take(_mr_legs(candles), candles, regime_def, macro,
                    "risk_off", cost_mult)
    return sorted(rt)


def control_rt(candles, macro, regime_def, kind, cost_mult=1.0):
    if kind == "always_trend":
        return sorted((ts, _charge(r, af, cost_mult))
                      for _, ts, r, af in _trend_legs(candles))
    if kind == "always_mr":
        return sorted((ts, _charge(r, af, cost_mult))
                      for _, ts, r, af in _mr_legs(candles))
    if kind == "swap":  # trend in risk_off, MR in risk_on (regime inverted)
        rt = _take(_trend_legs(candles), candles, regime_def, macro,
                   "risk_off", cost_mult)
        rt += _take(_mr_legs(candles), candles, regime_def, macro,
                    "risk_on", cost_mult)
        return sorted(rt)
    raise ValueError(f"unknown control kind: {kind}")
