"""Robustness battery for the system-level search. Each check is a frozen,
hand-testable gate run only on cells that already cleared DSR + ECON_BAR. A
cell failing ANY check is recorded `inconclusive`, never `edge`.

Cost-stress reuses single_trade_r's (net_r, atr_frac) and subtracts an extra
per-trade cost = extra_cost / atr_frac (same units as COST_FRACTION), so we
never mutate the global cost constant. No-lookahead is a causality check: the
generator's signal set on a truncated prefix must equal the full-data set on
that prefix (up to a boundary margin)."""
from __future__ import annotations

import math

from moonface.core.metrics import (COST_FRACTION, single_trade_r,
                                          summarize_r)
from moonface.core.risk import atr
from moonface.research.edge_search import net_trade_rs
from moonface.research.entries import PRICE_FAMILIES
from moonface.features.oi_features import nonoverlap

EXTRA_COST = 0.0005      # +5 bps/side stress on top of the modelled cost
DROP_FRAC = 0.05         # drop the top 5% winners for outlier-dependence
MIN_TRADES = 30          # minimum trades for an adequate sample
RECENT_FRAC = 0.2        # most-recent 20% of bars = the recent-period slice
LOOKAHEAD_MARGIN = 5     # boundary bars excluded from the causality compare


def trade_count_ok(rs: list[float], min_trades: int = MIN_TRADES) -> dict:
    return {"n": len(rs), "passed": len(rs) >= min_trades}


def outlier_dependence_ok(rs: list[float], drop_frac: float = DROP_FRAC) -> dict:
    base = summarize_r(rs).expectancy_r
    k = math.ceil(drop_frac * len(rs)) if rs else 0
    trimmed = sorted(rs, reverse=True)[k:] if k < len(rs) else []
    trimmed_exp = summarize_r(trimmed).expectancy_r
    return {"base_exp": base, "trimmed_exp": trimmed_exp, "dropped": k,
            "passed": bool(trimmed) and trimmed_exp > 0}


def cost_stress_ok(candles, family, params, exit_name, exit_params, h,
                   extra_cost: float = EXTRA_COST) -> dict:
    events = nonoverlap(PRICE_FAMILIES[family](candles, params), h)
    rs: list[float] = []
    for i, side in events:
        res = single_trade_r(candles, i, side, exit_name, exit_params)
        if res is None:
            continue
        net_r, atr_frac = res
        rs.append(net_r - extra_cost / atr_frac if atr_frac > 0 else net_r)
    s = summarize_r(rs)
    return {"expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "passed": s.expectancy_r > 0 and s.profit_factor > 1.0}


def cost_multiple_ok(candles, family, params, exit_name, exit_params, h,
                     mult: float) -> dict:
    """Multiplicative cost stress: charge `mult` x the modelled round-trip cost.

    The base cost (COST_FRACTION) is already inside single_trade_r's net_r, so an
    EXTRA (mult-1)*COST_FRACTION reaches a total of mult x cost. mult=1 reproduces
    the base series exactly; mult=2/3 are the user's 2x/3x robustness checks.
    Reuses cost_stress_ok's per-trade subtraction so the global cost is untouched.
    """
    extra = (mult - 1.0) * COST_FRACTION
    res = cost_stress_ok(candles, family, params, exit_name, exit_params, h, extra)
    return {**res, "mult": mult}


def recent_period_ok(full, family, params, exit_name, exit_params, h,
                     recent_bars: int) -> dict:
    window = full[-recent_bars:] if recent_bars < len(full) else full
    rs = net_trade_rs(window, family, params, exit_name, exit_params, h)
    s = summarize_r(rs)
    return {"expectancy_r": s.expectancy_r, "n": len(rs),
            "passed": len(rs) > 0 and s.expectancy_r > 0}


def regime_breakdown(full, family, params, exit_name, exit_params, h,
                     atr_period: int = 14) -> dict:
    """Split trades into high/low realised-vol regimes by the entry bar's ATR
    vs. the median ATR; require the majority regime profitable and the minority
    not catastrophic (expectancy > -0.1R)."""
    atrs = [atr(full[: i + 1], atr_period) for i in range(len(full))]
    valid = [a for a in atrs if a > 0]
    med = sorted(valid)[len(valid) // 2] if valid else 0.0
    events = nonoverlap(PRICE_FAMILIES[family](full, params), h)
    hi, lo = [], []
    for i, side in events:
        res = single_trade_r(full, i, side, exit_name, exit_params)
        if res is None:
            continue
        (hi if atrs[i] >= med else lo).append(res[0])
    hi_exp = summarize_r(hi).expectancy_r
    lo_exp = summarize_r(lo).expectancy_r
    major, minor = (hi_exp, lo_exp) if len(hi) >= len(lo) else (lo_exp, hi_exp)
    return {"hi_exp": hi_exp, "lo_exp": lo_exp, "hi_n": len(hi), "lo_n": len(lo),
            "passed": major > 0 and minor > -0.1}


def no_lookahead_ok(candles, family, params, split_k: int,
                    margin: int = LOOKAHEAD_MARGIN) -> dict:
    """Causality: entries computed on candles[:split_k] must match the full-data
    entries that fall in [0, split_k - margin). A generator that reads future
    bars produces a different prefix and fails."""
    gen = PRICE_FAMILIES[family]
    cutoff = split_k - margin
    full_pref = {(i, s) for i, s in gen(candles, params) if i < cutoff}
    trunc_pref = {(i, s) for i, s in gen(candles[:split_k], params) if i < cutoff}
    return {"matched": full_pref == trunc_pref, "passed": full_pref == trunc_pref}


def run_battery(train_oos, full, family, params, exit_name, exit_params, h, *,
                extra_cost=EXTRA_COST, drop_frac=DROP_FRAC, min_trades=MIN_TRADES,
                recent_frac=RECENT_FRAC, margin=LOOKAHEAD_MARGIN) -> dict:
    oos_rs = net_trade_rs(train_oos, family, params, exit_name, exit_params, h)
    checks = {
        "trade_count": trade_count_ok(oos_rs, min_trades),
        "outlier": outlier_dependence_ok(oos_rs, drop_frac),
        "cost_stress": cost_stress_ok(train_oos, family, params, exit_name,
                                      exit_params, h, extra_cost),
        "recent": recent_period_ok(full, family, params, exit_name, exit_params,
                                   h, int(recent_frac * len(full))),
        "regime": regime_breakdown(full, family, params, exit_name, exit_params,
                                   h, exit_params["atr_period"]),
        "no_lookahead": no_lookahead_ok(full, family, params, len(train_oos), margin),
    }
    return {"checks": checks, "passed": all(c["passed"] for c in checks.values())}
