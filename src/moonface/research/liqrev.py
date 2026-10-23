from __future__ import annotations

import math
from statistics import fmean

from moonface.core.models import Candle
from moonface.features.oi_features import binom_p_geq, nonoverlap, stouffer


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return math.inf
    ordered = sorted(xs)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def detect_events(candles: list[Candle], oi: list[float | None], *,
                  lookback: int, q: float) -> list[tuple[int, str]]:
    events: list[tuple[int, str]] = []
    returns: list[float] = [0.0]
    drops: list[float] = [0.0]
    for i in range(1, min(len(candles), len(oi))):
        prev_close = candles[i - 1].close
        ret = 0.0 if prev_close == 0.0 else math.log(candles[i].close / prev_close)
        prev_oi, cur_oi = oi[i - 1], oi[i]
        drop = 0.0
        if prev_oi is not None and cur_oi is not None and prev_oi > 0.0:
            drop = max(0.0, -(cur_oi / prev_oi - 1.0))
        if i >= lookback:
            ret_thr = _quantile([abs(x) for x in returns[i - lookback:i]], q)
            drop_thr = _quantile(drops[i - lookback:i], q)
            if abs(ret) > ret_thr and drop > drop_thr and ret != 0.0:
                events.append((i, "LONG" if ret < 0.0 else "SHORT"))
        returns.append(ret)
        drops.append(drop)
    return events


def event_net_returns(candles: list[Candle], events: list[tuple[int, str]], *,
                      h: int, cost: float) -> list[float]:
    closes = [c.close for c in candles]
    out: list[float] = []
    for i, side in events:
        if i + h >= len(closes) or closes[i] == 0.0:
            continue
        r = closes[i + h] / closes[i] - 1.0
        directional = r if side == "LONG" else -r
        out.append(directional - cost)
    return out


def nonoverlap_events(events: list[tuple[int, str]], h: int) -> list[tuple[int, str]]:
    return nonoverlap(events, h)


MIN_ASSETS = 8
MIN_EVENTS = 10
MIN_BREADTH = 12
STOUFFER_GATE = 2.0


def pooled(stats: list[dict]) -> dict:
    if not stats:
        return {"m": 0, "k_positive": 0, "p_sign": 1.0,
                "stouffer_z": 0.0, "pooled_mean": 0.0}
    k = sum(1 for s in stats if s["mean"] > 0.0)
    return {"m": len(stats), "k_positive": k,
            "p_sign": binom_p_geq(k, len(stats)),
            "stouffer_z": stouffer([s["t"] for s in stats]),
            "pooled_mean": fmean([s["mean"] for s in stats])}


def liqrev_verdict(stats: list[dict], robustness: dict, *,
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
                "reason": "net pooled mean reversion is non-positive"}
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