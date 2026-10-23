# src/moonface/core/exits.py
from __future__ import annotations

from collections.abc import Callable

from moonface.core.indicators import donchian_channel, ema
from moonface.core.risk import atr, horizon_r, risk_unit as _risk
from moonface.core.models import Candle

ExitFn = Callable[[int, str, list[Candle], dict], float | None]

_BRACKET_MAX_BARS = 96  # safety cap so a fixed bracket always terminates


def _r_unit(h1: list[Candle], i: int, atr_period: int) -> float | None:
    """The universal R denominator: 1 x ATR at the entry bar (lookahead-free).
    None when the entry is untradeable (last bar, or ATR <= 0)."""
    return _risk(h1, i, 1.0, atr_period)


def _fill(bar: Candle, side: str, stop: float | None,
          tp: float | None) -> float | None:
    """Pessimistic intrabar fill: when both stop and TP sit inside the bar's range,
    assume the stop fills first. Returns the fill price, or None if neither hit."""
    if side == "LONG":
        if stop is not None and bar.low <= stop:
            return stop
        if tp is not None and bar.high >= tp:
            return tp
    else:
        if stop is not None and bar.high >= stop:
            return stop
        if tp is not None and bar.low <= tp:
            return tp
    return None


def horizon_hold(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Validation baseline: hold n_bars, no stop. R = forward move / 1*ATR."""
    return horizon_r(i, side, h1, 1.0, params["atr_period"], params["n_bars"])


def horizon_wide_stop(i: int, side: str, h1: list[Candle],
                      params: dict) -> float | None:
    """Hold n_bars, but exit early if a static k_stop*ATR stop is hit."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    n_bars, k_stop = params["n_bars"], params["k_stop"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    end = min(i + n_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        hit = _fill(h1[j], side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
    return round(sign * (h1[end].close - entry) / unit, 4)


def fixed_bracket(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Static stop k_stop*ATR and TP m_tp*ATR, capped at _BRACKET_MAX_BARS."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    k_stop, m_tp = params["k_stop"], params["m_tp"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    if side == "LONG":
        stop, tp = entry - k_stop * unit, entry + m_tp * unit
    else:
        stop, tp = entry + k_stop * unit, entry - m_tp * unit
    end = min(i + _BRACKET_MAX_BARS, len(h1) - 1)
    for j in range(i + 1, end + 1):
        hit = _fill(h1[j], side, stop, tp)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
    return round(sign * (h1[end].close - entry) / unit, 4)


def atr_trail(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Trail a stop at k_trail*ATR from the running extreme, no TP, cap at max_bars.
    The stop in force during bar j is the one set after bar j-1's extreme."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    k_trail, max_bars = params["k_trail"], params["max_bars"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    trail = k_trail * unit
    extreme = entry
    stop = entry - trail if side == "LONG" else entry + trail
    end = min(i + max_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
        if side == "LONG":
            extreme = max(extreme, bar.high)
            stop = max(stop, extreme - trail)
        else:
            extreme = min(extreme, bar.low)
            stop = min(stop, extreme + trail)
    return round(sign * (h1[end].close - entry) / unit, 4)


def donchian_trail(i: int, side: str, h1: list[Candle],
                   params: dict) -> float | None:
    """Donchian-channel trailing stop — the deployable Slice-2 swing exit.

    Initial stop is entry -/+ k_stop*ATR; thereafter it is ratcheted toward
    price by the prior trail_n channel extreme (a long's stop only rises to the
    prior-trail_n low, a short's only falls to the prior-trail_n high). This is
    the exact mechanic of trend_sim._run_position, expressed in the registry's
    gross-R-in-ATR-units convention (costs are applied by single_trade_r).
    Optional max_bars caps the hold for parity with the other exits; omitted, the
    position is marked to the final available close like trend_sim.
    """
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    k_stop, trail_n = params["k_stop"], params["trail_n"]
    max_bars = params.get("max_bars")
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    end = len(h1) - 1 if max_bars is None else min(i + max_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        if j >= trail_n:  # prior trail_n channel, excluding bar j (lookahead-free)
            window = h1[j - trail_n:j]
            if side == "LONG":
                stop = max(stop, min(c.low for c in window))
            else:
                stop = min(stop, max(c.high for c in window))
        hit = _fill(h1[j], side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
    return round(sign * (h1[end].close - entry) / unit, 4)


def breakeven_horizon(i: int, side: str, h1: list[Candle],
                      params: dict) -> float | None:
    """Hold n_bars with an initial k_stop*ATR stop; once price reaches +1R favorable,
    move the stop to entry (breakeven). Arming happens after the bar's fill check."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    n_bars, k_stop = params["n_bars"], params["k_stop"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    target = entry + unit if side == "LONG" else entry - unit
    armed = False
    end = min(i + n_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
        if not armed:
            reached = bar.high >= target if side == "LONG" else bar.low <= target
            if reached:
                stop = entry
                armed = True
    return round(sign * (h1[end].close - entry) / unit, 4)


def _reclaim_ref(h1: list[Candle], j: int, ref_mode: str,
                 ref_n: int) -> float | None:
    """Reference level at bar j using only bars at/<=j (lookahead-free)."""
    if ref_mode == "ema":
        window = [c.close for c in h1[max(0, j + 1 - 4 * ref_n): j + 1]]
        if len(window) < ref_n:
            return None
        return ema(window, ref_n)
    if ref_mode == "range_mid":
        if j < ref_n:
            return None
        prior_high, prior_low = donchian_channel(h1, j, ref_n)
        return (prior_high + prior_low) / 2.0
    raise ValueError(f"unknown ref mode {ref_mode!r}")


def mean_revert_reclaim(i: int, side: str, h1: list[Candle],
                        params: dict) -> float | None:
    """Mean-reversion exit: close out when price reclaims a reference (EMA or the
    prior-range midpoint); else a protective k_stop*ATR stop; else mark out at
    max_bars. Returns gross R in 1*ATR units (costs applied by single_trade_r)."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    ref_mode, ref_n = params["ref"], params["ref_n"]
    k_stop, max_bars = params["k_stop"], params["max_bars"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    end = min(i + max_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
        ref = _reclaim_ref(h1, j, ref_mode, ref_n)
        if ref is not None:
            reclaimed = bar.close >= ref if side == "LONG" else bar.close <= ref
            if reclaimed:
                return round(sign * (bar.close - entry) / unit, 4)
    return round(sign * (h1[end].close - entry) / unit, 4)


def chandelier(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Chandelier trailing stop: offset atr_mult*ATR from the running extreme, with
    ATR RECOMPUTED each bar (vs atr_trail's fixed entry ATR). The stop active during
    bar j uses the extreme and ATR through bar j-1 (lookahead-free). Caps at max_bars.
    Returns gross R in 1*ATR-at-entry units (costs applied by single_trade_r)."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    atr_mult, max_bars, atr_period = (params["atr_mult"], params["max_bars"],
                                      params["atr_period"])
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    extreme = entry
    end = min(i + max_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        a_prev = atr(h1[:j], atr_period)  # ATR through bar j-1, lookahead-free
        if a_prev > 0:
            stop = (extreme - atr_mult * a_prev if side == "LONG"
                    else extreme + atr_mult * a_prev)
            hit = _fill(h1[j], side, stop, None)
            if hit is not None:
                return round(sign * (hit - entry) / unit, 4)
        if side == "LONG":
            extreme = max(extreme, h1[j].high)
        else:
            extreme = min(extreme, h1[j].low)
    return round(sign * (h1[end].close - entry) / unit, 4)


_AP = 14  # atr_period used across the registry

# name -> (exit_fn, list of param dicts). Grids kept small (YAGNI).
EXIT_REGISTRY: dict[str, tuple] = {
    "horizon_hold": (horizon_hold, [
        {"n_bars": 12, "atr_period": _AP},
        {"n_bars": 24, "atr_period": _AP},
        {"n_bars": 48, "atr_period": _AP}]),
    "atr_trail": (atr_trail, [
        {"k_trail": 2.0, "max_bars": 48, "atr_period": _AP},
        {"k_trail": 3.0, "max_bars": 48, "atr_period": _AP}]),
    "horizon_wide_stop": (horizon_wide_stop, [
        {"n_bars": 24, "k_stop": 2.5, "atr_period": _AP},
        {"n_bars": 24, "k_stop": 3.0, "atr_period": _AP}]),
    "breakeven_horizon": (breakeven_horizon, [
        {"n_bars": 24, "k_stop": 3.0, "atr_period": _AP}]),
    "fixed_bracket": (fixed_bracket, [
        {"k_stop": 1.0, "m_tp": 4.0, "atr_period": _AP},
        {"k_stop": 2.0, "m_tp": 4.0, "atr_period": _AP}]),
}

# Deployment-only exits. These are usable by a promoted strategy and scored by
# the forward gate, but are deliberately kept OUT of EXIT_REGISTRY so they never
# enter a pre-registered research search grid (which would retroactively change
# DSR calibration on already-concluded domains). The grid here is documentation
# of the frozen Slice-2 params; it is never swept.
DEPLOY_EXIT_REGISTRY: dict[str, tuple] = {
    "donchian_trail": (donchian_trail, [
        {"k_stop": 2.0, "trail_n": 20, "atr_period": _AP}]),
}

# Practical-lane exit set: usable/resolvable (folded into EXECUTABLE_EXITS so
# single_trade_r can run it) but deliberately kept OUT of EXIT_REGISTRY so the
# academic research grid — and every concluded domain's DSR calibration — is
# unchanged. The param grid here is documentation; the practical lane builds its
# own timeframe-scaled param sets in research/practical/exits_scaled.py.
PRACTICAL_EXIT_REGISTRY: dict[str, tuple] = {
    "mean_revert_reclaim": (mean_revert_reclaim, [
        {"ref": "ema", "ref_n": 20, "k_stop": 2.5, "max_bars": 48, "atr_period": _AP},
        {"ref": "range_mid", "ref_n": 20, "k_stop": 2.5, "max_bars": 48, "atr_period": _AP}]),
}

# BTC-Specialized lane exit set: resolvable for single_trade_r but kept OUT of
# EXIT_REGISTRY so the academic grid / every concluded domain's DSR calibration is
# unchanged. The btcspec lane builds its own TF-scaled param sets in
# research/btcspec/exits_scaled.py; the grid here is documentation only.
BTCSPEC_EXIT_REGISTRY: dict[str, tuple] = {
    "chandelier": (chandelier, [
        {"atr_mult": 3.0, "max_bars": 60, "atr_period": _AP},
        {"atr_mult": 4.0, "max_bars": 60, "atr_period": _AP}]),
}

# Every exit a promoted strategy may name / the forward gate may execute:
# the research search set plus the deployment-only set.
EXECUTABLE_EXITS: dict[str, tuple] = {
    **EXIT_REGISTRY, **DEPLOY_EXIT_REGISTRY, **PRACTICAL_EXIT_REGISTRY,
    **BTCSPEC_EXIT_REGISTRY}

# --- additive span resolvers (portfolio lane) ---------------------------------
# These mirror the exit fns above but ALSO return the exit-bar index, which the
# gross-R-only exit fns discard. gross_r is computed identically; a cross-check
# test asserts span gross == exit-fn gross. single_trade_r is unchanged.

SpanFn = Callable[[int, str, list[Candle], dict], tuple[int, float] | None]


def horizon_hold_span(i: int, side: str, h1: list[Candle],
                      params: dict) -> tuple[int, float] | None:
    """(exit_idx, gross_r) for horizon_hold. exit_idx = min(i+n_bars, len-1)."""
    r = horizon_r(i, side, h1, 1.0, params["atr_period"], params["n_bars"])
    if r is None:
        return None
    exit_idx = min(i + params["n_bars"], len(h1) - 1)
    return exit_idx, r


def horizon_wide_stop_span(i: int, side: str, h1: list[Candle],
                           params: dict) -> tuple[int, float] | None:
    """(exit_idx, gross_r) mirroring horizon_wide_stop exactly."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    n_bars, k_stop = params["n_bars"], params["k_stop"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    end = min(i + n_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        hit = _fill(h1[j], side, stop, None)
        if hit is not None:
            return j, round(sign * (hit - entry) / unit, 4)
    return end, round(sign * (h1[end].close - entry) / unit, 4)


def atr_trail_span(i: int, side: str, h1: list[Candle],
                   params: dict) -> tuple[int, float] | None:
    """(exit_idx, gross_r) mirroring atr_trail exactly."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    k_trail, max_bars = params["k_trail"], params["max_bars"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    trail = k_trail * unit
    extreme = entry
    stop = entry - trail if side == "LONG" else entry + trail
    end = min(i + max_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            return j, round(sign * (hit - entry) / unit, 4)
        if side == "LONG":
            extreme = max(extreme, bar.high)
            stop = max(stop, extreme - trail)
        else:
            extreme = min(extreme, bar.low)
            stop = min(stop, extreme + trail)
    return end, round(sign * (h1[end].close - entry) / unit, 4)


def fixed_bracket_span(i: int, side: str, h1: list[Candle],
                       params: dict) -> tuple[int, float] | None:
    """(exit_idx, gross_r) mirroring fixed_bracket exactly."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    k_stop, m_tp = params["k_stop"], params["m_tp"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    if side == "LONG":
        stop, tp = entry - k_stop * unit, entry + m_tp * unit
    else:
        stop, tp = entry + k_stop * unit, entry - m_tp * unit
    end = min(i + _BRACKET_MAX_BARS, len(h1) - 1)
    for j in range(i + 1, end + 1):
        hit = _fill(h1[j], side, stop, tp)
        if hit is not None:
            return j, round(sign * (hit - entry) / unit, 4)
    return end, round(sign * (h1[end].close - entry) / unit, 4)


_SPAN_FNS: dict[str, SpanFn] = {
    "horizon_hold": horizon_hold_span,
    "atr_trail": atr_trail_span,
    "horizon_wide_stop": horizon_wide_stop_span,
    "fixed_bracket": fixed_bracket_span,
}
