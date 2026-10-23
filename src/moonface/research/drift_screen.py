# src/moonface/research/drift_screen.py
"""Exit-free, path-aware cross-asset mechanism screen — pure statistics.

Generalizes oibuild_study with a per-event maximum adverse excursion (MAE)
measured in R (excursion / ATR-at-entry), so directional drift is judged
against the drawdown it lived through. No exits, stops, TPs, or grids: a
single fixed horizon h. Design frozen in
experiments/drift_screen/PREREGISTRATION.md."""
from __future__ import annotations

from collections.abc import Callable
from statistics import fmean

from moonface.research.edge.evaluate import _risk
from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.features.oi_features import (asset_stats, binom_p_geq,
                                             nonoverlap, stouffer,
                                             SIGN_ALPHA, STOUFFER_CRIT,
                                             MIN_ASSETS, MIN_EVENTS_PER_ASSET)


def event_outcome(candles: list[Candle], i: int, side: str, h: int,
                  atr_period: int) -> tuple[float, float, float] | None:
    """Per-event (ret_r, mae_r, mfe_r) in R units over a fixed horizon h.

    ret_r = side * (close[i+h] - close[i]) / unit   (forward move in R)
    mae_r = worst intra-horizon excursion AGAINST the position, <= 0
            (bar.low for LONG, bar.high for SHORT).
    mfe_r = best intra-horizon excursion IN FAVOUR, >= 0
            (bar.high for LONG, bar.low for SHORT).
    Returns None when the entry is untradeable (unit None) or there are
    fewer than h future bars."""
    unit = _risk(candles, i, 1.0, atr_period)
    if unit is None or i + h >= len(candles):
        return None
    entry = candles[i].close
    sign = 1.0 if side == "LONG" else -1.0
    ret_r = sign * (candles[i + h].close - entry) / unit
    worst = 0.0
    best = 0.0
    for k in range(1, h + 1):
        bar = candles[i + k]
        adverse = (bar.low - entry) if side == "LONG" else (entry - bar.high)
        favorable = (bar.high - entry) if side == "LONG" else (entry - bar.low)
        worst = min(worst, adverse / unit)
        best = max(best, favorable / unit)
    return ret_r, worst, best


def asset_path_stats(outcomes: list[tuple[float, float, float]]) -> dict:
    """One asset's evidence: mean forward R, mean absolute adverse R, mean
    favorable R, the per-event positive sign rate, and the ret_r t-stat
    (reusing oibuild's asset_stats so the magnitude test is identical across
    studies)."""
    if not outcomes:
        return {"n": 0, "mean_ret_r": 0.0, "mean_abs_mae_r": 0.0,
                "mean_mfe_r": 0.0, "sign_rate": 0.0, "t": 0.0}
    rets = [r for r, _, _ in outcomes]
    maes = [abs(m) for _, m, _ in outcomes]
    mfes = [f for _, _, f in outcomes]
    base = asset_stats(rets)
    pos = sum(1 for r in rets if r > 0)
    return {"n": base["n"], "mean_ret_r": base["mean"],
            "mean_abs_mae_r": fmean(maes), "mean_mfe_r": fmean(mfes),
            "sign_rate": pos / len(rets), "t": base["t"]}


def drift_verdict(stats: list[dict], floor: float,
                  min_assets: int = MIN_ASSETS) -> dict:
    """Two-part pooled gate (both frozen before the run):
      1. drift exists  -> sign test p<=0.05 AND Stouffer Z>=1.645 on ret_r
      2. drift survives -> pooled mean_ret_r / pooled mean_abs_mae_r >= floor
    Tripartite verdict, mirroring oibuild_study.verdict_from."""
    m = len(stats)
    base = {"m_assets": m, "p_sign": None, "stouffer_z": None,
            "pooled_ret_r": None, "pooled_abs_mae_r": None, "ratio": None,
            "reason": ""}
    if m < min_assets:
        return {**base, "verdict": "inconclusive",
                "reason": f"insufficient evaluable assets ({m} < {min_assets})"}
    k = sum(1 for s in stats if s["mean_ret_r"] > 0)
    p_sign = binom_p_geq(k, m)
    z = stouffer([s["t"] for s in stats])
    pooled_ret = fmean([s["mean_ret_r"] for s in stats])
    pooled_mae = fmean([s["mean_abs_mae_r"] for s in stats])
    ratio = pooled_ret / pooled_mae if pooled_mae > 0 else 0.0
    base.update(k_positive=k, p_sign=p_sign, stouffer_z=z,
                pooled_ret_r=pooled_ret, pooled_abs_mae_r=pooled_mae,
                ratio=ratio)
    drift = p_sign <= SIGN_ALPHA and z >= STOUFFER_CRIT
    if drift and ratio >= floor:
        return {**base, "verdict": "mechanism_exists",
                "reason": f"breadth p={p_sign:.4g}, Z={z:.2f}, and path "
                          f"ratio={ratio:.3f} >= floor {floor:.3f}"}
    if pooled_ret <= 0.0 or not drift:
        return {**base, "verdict": "mechanism_does_not_exist",
                "reason": f"drift gate not cleared (p={p_sign:.4g}, "
                          f"Z={z:.2f}, pooled_ret_r={pooled_ret:.4f})"}
    return {**base, "verdict": "inconclusive",
            "reason": f"drift present but path ratio={ratio:.3f} < floor "
                      f"{floor:.3f} (drift unacceptable for its drawdown)"}


Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]


def score_signal_on_asset(candles: list[Candle], generator: Generator,
                          params: dict, h: int, atr_period: int) -> dict:
    """Run one signal generator on one asset, drop serially-overlapping
    events (h-bar non-overlap), compute per-event path outcomes, return the
    per-asset path stats."""
    events = nonoverlap(generator(candles, params), h)
    outcomes: list[tuple[float, float, float]] = []
    for i, side in events:
        out = event_outcome(candles, i, side, h, atr_period)
        if out is not None:
            outcomes.append(out)
    return asset_path_stats(outcomes)


def screen_signal(name: str, generator: Generator, params: dict,
                  pool: dict[str, list[Candle]], h: int, atr_period: int,
                  floor: float, min_events: int = MIN_EVENTS_PER_ASSET,
                  min_assets: int = MIN_ASSETS) -> dict:
    """Screen one signal across the fresh-asset pool. Each asset with at least
    min_events non-overlapping tradeable events is one unit of evidence; the
    pooled two-part verdict is computed over those assets."""
    per_asset: list[dict] = []
    for sym in sorted(pool):
        stats = score_signal_on_asset(pool[sym], generator, params, h,
                                      atr_period)
        if stats["n"] >= min_events:
            per_asset.append({"sym": sym, **stats})
    verdict = drift_verdict(per_asset, floor=floor, min_assets=min_assets)
    return {"signal": name, "params": params, "h": h,
            "assets": per_asset, "verdict": verdict}


def score_family_on_asset(family: str, params: dict, bundle: DataBundle,
                          h: int, atr_period: int) -> dict:
    """Bundle-aware sibling of score_signal_on_asset: resolve events through
    generate_entries (so funding/positioning/orderbook families work), drop
    serially-overlapping events, and return the per-asset path stats. An asset
    whose bundle lacks the family's required data raises inside generate_entries
    and is treated as zero-evidence by the caller."""
    events = nonoverlap(generate_entries(family, params, bundle), h)
    outcomes: list[tuple[float, float, float]] = []
    for i, side in events:
        out = event_outcome(bundle.candles, i, side, h, atr_period)
        if out is not None:
            outcomes.append(out)
    return asset_path_stats(outcomes)


def screen_family(family: str, params: dict,
                  pool: dict[str, DataBundle], h: int, atr_period: int,
                  floor: float, min_events: int = MIN_EVENTS_PER_ASSET,
                  min_assets: int = MIN_ASSETS) -> dict:
    """Screen one family across a per-asset DataBundle pool. Each asset with at
    least min_events non-overlapping tradeable events is one unit of evidence.
    An asset whose bundle lacks the family's data (generate_entries raises
    ValueError) contributes no evidence and is skipped."""
    per_asset: list[dict] = []
    for sym in sorted(pool):
        try:
            stats = score_family_on_asset(family, params, pool[sym], h,
                                           atr_period)
        except ValueError:
            continue
        if stats["n"] >= min_events:
            per_asset.append({"sym": sym, **stats})
    verdict = drift_verdict(per_asset, floor=floor, min_assets=min_assets)
    return {"signal": family, "params": params, "h": h,
            "assets": per_asset, "verdict": verdict}


def horizon_curve(family: str, params: dict, pool: dict[str, DataBundle],
                  horizons: list[int], atr_period: int,
                  min_events: int = MIN_EVENTS_PER_ASSET,
                  min_assets: int = MIN_ASSETS) -> list[dict]:
    """Descriptive term structure: pooled stats at each horizon. NOT a gate —
    no floor, no PASS/FAIL. Renders evidence of drift shape/decay only. The
    binding verdict is screen_family at the frozen primary horizon."""
    rows: list[dict] = []
    for h in horizons:
        per_asset = []
        for sym in sorted(pool):
            try:
                s = score_family_on_asset(family, params, pool[sym], h,
                                          atr_period)
            except ValueError:
                continue
            if s["n"] >= min_events:
                per_asset.append(s)
        m = len(per_asset)
        if m < min_assets:
            rows.append({"h": h, "m_assets": m, "pooled": False,
                         "pooled_ret_r": None, "pooled_sign_rate": None,
                         "pooled_abs_mae_r": None, "pooled_mfe_r": None,
                         "stouffer_z": None})
            continue
        rows.append({
            "h": h, "m_assets": m, "pooled": True,
            "pooled_ret_r": fmean([s["mean_ret_r"] for s in per_asset]),
            "pooled_sign_rate": fmean([s["sign_rate"] for s in per_asset]),
            "pooled_abs_mae_r": fmean([s["mean_abs_mae_r"] for s in per_asset]),
            "pooled_mfe_r": fmean([s["mean_mfe_r"] for s in per_asset]),
            "stouffer_z": stouffer([s["t"] for s in per_asset])})
    return rows
