# src/moonface/research/liqladder.py
"""Pooled cross-asset test of the liquidation-ladder magnet mechanism — pure
statistics.

Design frozen in experiments/liqladder/PREREGISTRATION.md. The ladder is an
ex-ante estimate of pending liquidation levels, built from open-interest
increments (entry prices) split by the long/short account ratio across fixed
leverage tiers. The hypothesis is directional CONTINUATION toward the heavy
side of the ladder — the inverse orientation of the closed liqrev reversion
lane, which traded the aftermath of the collapse rather than the approach.
Events come from a single frozen trigger, outcomes are net directional
forward returns, and the verdict is the pre-registered gate. Each asset is
one unit of evidence; raw events are never pooled across assets."""
from __future__ import annotations

import math

from moonface.core.models import Candle
from moonface.research.liqrev import event_net_returns, pooled
from moonface.features.oi_features import nonoverlap

BIN_W = 1.0025            # multiplicative price-bin width (0.25%)
TIERS = (10.0, 25.0, 50.0, 100.0)
TIER_W = 0.25
MMR = 0.005               # maintenance-margin adjustment on liq distance
DELTA = 0.05              # ladder window: +/- 5% of spot
A_THR = 0.6               # |asymmetry| trigger
DENSE_Q = 0.9             # dense bin = top decile of window bin masses
ATR_PERIOD = 14
ATR_K = 1.0               # nearest dense bin must sit within 1 ATR

MIN_ASSETS = 8
MIN_EVENTS = 10
MIN_BREADTH = 12
STOUFFER_GATE = 2.0

_LN_BIN = math.log(BIN_W)

__all__ = ["detect_events", "event_net_returns", "nonoverlap_events",
           "atr_series", "liqladder_verdict", "pooled",
           "MIN_ASSETS", "MIN_EVENTS"]


def _bin_idx(price: float) -> int:
    return math.floor(math.log(price) / _LN_BIN)


def _bin_mid(idx: int) -> float:
    return BIN_W ** (idx + 0.5)


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return math.inf
    ordered = sorted(xs)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def atr_series(candles: list[Candle], period: int = ATR_PERIOD) -> list[float]:
    """ATR at every prefix, equal to foundation.risk.atr(candles[:i+1], period)
    but computed in one pass (the per-bar slice-and-recompute is quadratic)."""
    trs: list[float] = []
    for i, c in enumerate(candles):
        prev_close = candles[i - 1].close if i > 0 else c.close
        trs.append(max(c.high - c.low, abs(c.high - prev_close),
                       abs(c.low - prev_close)))
    out: list[float] = []
    run = 0.0
    for i in range(len(candles)):
        run += trs[i]
        if i >= period:
            run -= trs[i - period]
        out.append(0.0 if i < 1 else run / min(i + 1, period))
    return out


def detect_events(candles: list[Candle], oi: list[float | None],
                  ls_ratio: list[float | None], *, delta: float = DELTA,
                  a_thr: float = A_THR, dense_q: float = DENSE_Q,
                  atr_period: int = ATR_PERIOD,
                  atr_k: float = ATR_K) -> list[tuple[int, str]]:
    """One pass over aligned bars maintaining the estimated liquidation ladder.

    Per bar, in order: (1) bins traversed by the bar's range are consumed —
    their stops fired; (2) OI growth adds mass at the tier liquidation levels
    of positions opened near the close, OI shrinkage decays the whole ladder
    proportionally (voluntary closes); (3) the asymmetry of ladder mass within
    +/- delta of spot fires a trigger toward the heavy side when a dense bin
    sits within atr_k * ATR. All state uses bars <= i only."""
    events: list[tuple[int, str]] = []
    ladder: dict[int, float] = {}
    scale = 1.0  # global decay factor so proportional shrink is O(1)
    atrs = atr_series(candles, atr_period)
    n = min(len(candles), len(oi), len(ls_ratio))
    win_bins = int(math.log1p(delta) / _LN_BIN) + 1
    for i in range(1, n):
        c = candles[i]
        if c.low > 0.0:
            for b in range(_bin_idx(c.low), _bin_idx(c.high) + 1):
                ladder.pop(b, None)
        prev_oi, cur_oi = oi[i - 1], oi[i]
        if (prev_oi is not None and cur_oi is not None and prev_oi > 0.0
                and c.close > 0.0):
            d_oi = cur_oi - prev_oi
            if d_oi > 0.0:
                r = ls_ratio[i]
                fl = r / (1.0 + r) if r is not None and r >= 0.0 else 0.5
                for lev in TIERS:
                    add = d_oi * TIER_W / scale
                    lo = _bin_idx(c.close * (1.0 - 1.0 / lev + MMR))
                    hi = _bin_idx(c.close * (1.0 + 1.0 / lev - MMR))
                    ladder[lo] = ladder.get(lo, 0.0) + add * fl
                    ladder[hi] = ladder.get(hi, 0.0) + add * (1.0 - fl)
            elif d_oi < 0.0:
                factor = cur_oi / prev_oi
                if factor <= 0.0:
                    ladder.clear()
                    scale = 1.0
                else:
                    scale *= factor
        if i < atr_period or c.close <= 0.0 or atrs[i] <= 0.0:
            continue
        spot = c.close
        sb = _bin_idx(spot)
        window = [(b, m) for b in range(sb - win_bins, sb + win_bins + 1)
                  if (m := ladder.get(b, 0.0)) > 0.0
                  and spot * (1.0 - delta) <= _bin_mid(b) <= spot * (1.0 + delta)]
        d_down = sum(m for b, m in window if _bin_mid(b) < spot)
        d_up = sum(m for b, m in window if _bin_mid(b) > spot)
        total = d_down + d_up
        if total <= 0.0:
            continue
        asym = (d_down - d_up) / total
        if abs(asym) <= a_thr:
            continue
        side = "SHORT" if asym > 0.0 else "LONG"
        thr = _quantile([m for _, m in window], dense_q)
        dense = [b for b, m in window
                 if m >= thr and (_bin_mid(b) < spot) == (side == "SHORT")]
        if not dense:
            continue
        if min(abs(_bin_mid(b) - spot) for b in dense) < atr_k * atrs[i]:
            events.append((i, side))
    return events


def nonoverlap_events(events: list[tuple[int, str]],
                      h: int) -> list[tuple[int, str]]:
    return nonoverlap(events, h)


def liqladder_verdict(stats: list[dict], robustness: dict, *,
                      min_assets: int = MIN_ASSETS) -> dict:
    p = pooled(stats)
    base = {"m_assets": p["m"], "k_positive": p["k_positive"],
            "p_sign": p["p_sign"], "stouffer_z": p["stouffer_z"],
            "pooled_mean": p["pooled_mean"]}
    if p["m"] < min_assets:
        return {**base, "verdict": "inconclusive",
                "reason": f"insufficient evaluable assets ({p['m']} < {min_assets})"}
    if p["pooled_mean"] <= 0.0:
        return {**base, "verdict": "mechanism_does_not_exist",
                "reason": "net pooled mean continuation is non-positive"}
    gate = p["stouffer_z"] > STOUFFER_GATE and p["k_positive"] >= MIN_BREADTH
    robust = (
        robustness["time_first_half"]["pooled_mean"] > 0.0
        and robustness["time_second_half"]["pooled_mean"] > 0.0
        and robustness["leave_one_out_pooled_mean"]["min"] > 0.0
    )
    if gate and robust:
        return {**base, "verdict": "mechanism_exists",
                "reason": "net Stouffer, breadth, time halves, and leave-one-out all clear"}
    if not robust:
        return {**base, "verdict": "non_robust",
                "reason": "positive pooled effect fails time-half or leave-one-out robustness"}
    return {**base, "verdict": "inconclusive",
            "reason": "positive pooled effect misses the frozen Z or breadth gate"}
