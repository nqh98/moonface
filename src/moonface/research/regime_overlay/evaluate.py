from __future__ import annotations

from dataclasses import replace

from moonface.core.metrics import summarize_r
from moonface.research.regime_overlay.overlay import apply_overlay
from moonface.research.trend_sim import simulate_donchian

_YEAR_MS = 365 * 24 * 3_600_000


def vector_from_rt(rt: list[tuple[int, float]], first_ts: int, last_ts: int) -> dict:
    rs = [r for _, r in rt]
    s = summarize_r(rs)
    cut = last_ts - _YEAR_MS
    trailing = round(sum(r for ts, r in rt if ts >= cut), 4)
    ex_best1 = round(s.total_r - (max(rs) if rs else 0.0), 4)
    pf = s.profit_factor
    return {
        "trades": s.trade_count,
        "net_r": s.total_r,
        "expectancy_r": s.expectancy_r,
        "profit_factor": pf if pf != float("inf") else None,
        "max_drawdown_r": s.max_drawdown_r,
        "trailing_365d_net_r": trailing,
        "net_r_ex_best1": ex_best1,
    }


def _sim_params(params, mode):
    # The byte-identical deployed base is long-only. "directional" sources shorts
    # from a long+short sim (longs kept in risk_on, shorts in risk_off by the
    # overlay); "derisk"/"size" operate on the long-only base. The comparison
    # control (base_vector) is ALWAYS the long-only config.
    return replace(params, long_only=False) if mode == "directional" else params


def _overlaid_rt(candles, funding, params, regime_def, macro, mode):
    trades = simulate_donchian(candles, _sim_params(params, mode), funding)
    return apply_overlay(trades, candles, regime_def, macro, mode)


def _cost_stress(candles, funding, base_params, regime_def, macro, mode):
    out = {}
    for mult, key in ((1.0, "net_r_1x"), (2.0, "net_r_2x"), (3.0, "net_r_3x")):
        p = replace(base_params,
                    fee_rate=base_params.fee_rate * mult,
                    slippage=base_params.slippage * mult)
        rt = _overlaid_rt(candles, funding, p, regime_def, macro, mode)
        out[key] = round(sum(r for _, r in rt), 4)
    return out


def cell_vector(candles, funding, base_params, regime_def, macro, mode,
                first_ts, last_ts) -> dict:
    rt = _overlaid_rt(candles, funding, base_params, regime_def, macro, mode)
    v = vector_from_rt(rt, first_ts, last_ts)
    v["cost_stress"] = _cost_stress(candles, funding, base_params,
                                    regime_def, macro, mode)
    return v


def base_vector(candles, funding, base_params, first_ts, last_ts) -> dict:
    trades = simulate_donchian(candles, base_params, funding)
    rt = [(candles[t.exit_index].timestamp_ms, t.r_multiple) for t in trades]
    v = vector_from_rt(rt, first_ts, last_ts)
    cs = {}
    for mult, key in ((1.0, "net_r_1x"), (2.0, "net_r_2x"), (3.0, "net_r_3x")):
        p = replace(base_params, fee_rate=base_params.fee_rate * mult,
                    slippage=base_params.slippage * mult)
        tt = simulate_donchian(candles, p, funding)
        cs[key] = round(sum(t.r_multiple for t in tt), 4)
    v["cost_stress"] = cs
    return v


def practical_pass(vec: dict, min_trades: int = 30, max_dd_r: float = -30.0) -> dict:
    cs = vec.get("cost_stress", {})
    out = {
        "net_positive": vec["net_r"] > 0,
        "drawdown_ok": vec["max_drawdown_r"] >= max_dd_r,
        "enough_trades": vec["trades"] >= min_trades,
        "outlier_ok": vec["net_r_ex_best1"] > 0,
        "cost_2x_ok": cs.get("net_r_2x", -1.0) > 0,
        "cost_3x_ok": cs.get("net_r_3x", -1.0) > 0,
    }
    out["all_pass"] = all(out.values())
    return out


def beats_base(cell: dict, base: dict) -> dict:
    return {
        "delta_net_r": round(cell["net_r"] - base["net_r"], 4),
        "delta_max_dd_r": round(cell["max_drawdown_r"] - base["max_drawdown_r"], 4),
        "delta_trailing_365d": round(
            cell["trailing_365d_net_r"] - base["trailing_365d_net_r"], 4),
        "beats_recent": cell["trailing_365d_net_r"] > base["trailing_365d_net_r"],
    }
