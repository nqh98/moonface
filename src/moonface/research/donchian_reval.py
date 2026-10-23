"""Pre-registered BTC 4h Donchian revalidation (single asset, paper-only).

Reuses the frozen engines: trend_sim (exit-driven trend follower), edge_search
(gross fixed-horizon probe), metrics, econ. See
docs/research-log/specs/2026-06-20-btc-4h-donchian-revalidation-design.md."""
from __future__ import annotations

from dataclasses import dataclass, replace

from moonface.core.indicators import sma
from moonface.core.metrics import summarize_r
from moonface.core.risk import atr as _atr_fn
from moonface.kernel.econ import ECON_BAR, _mar, evaluate_econ
from moonface.research.edge_search import prescreen
from moonface.research.trend_sim import TrendParams, simulate_donchian
from moonface.kernel.walkforward import walk_forward

H_FIXED = 12  # fixed-horizon bars (matches edge-search Stage-1 h)


def gross_h12_probe(candles, n=40, h=H_FIXED, atr_period=14) -> dict:
    """Simulator-FREE gross fixed-horizon drift probe — reproduces edge-search
    Stage-1 for Donchian-n. Distinct from net_fixed_horizon_exit (a costed
    simulator trade)."""
    s1 = prescreen(candles, "donchian_break", {"n": n, "long_only": True}, h, atr_period)
    return {"n": s1["n"], "z": s1["z"], "mean_ret_r": s1["mean_ret_r"],
            "sign_rate": s1["sign_rate"], "passed": s1["passed"]}


def _summary_row(rs: list[float]) -> dict:
    s = summarize_r(rs)
    return {"n": s.trade_count, "expectancy_r": s.expectancy_r,
            "profit_factor": s.profit_factor, "max_dd_r": s.max_drawdown_r,
            "total_r": s.total_r, "mar": round(_mar(s), 4)}


def exit_ablation(candles, funding, base_params: TrendParams) -> dict:
    """Same Donchian entries, three exits via the one cost/funding accounting."""
    arms = {
        "net_fixed_horizon_exit": replace(base_params, exit_mode="fixed_horizon", fh_bars=H_FIXED),
        "stop_only": replace(base_params, exit_mode="stop_only"),
        "trail": replace(base_params, exit_mode="trail"),
    }
    out = {}
    for name, p in arms.items():
        rs = [t.r_multiple for t in simulate_donchian(candles, p, funding)]
        out[name] = _summary_row(rs)
    return out


def ea_pass(ablation: dict) -> bool:
    """Trail must materially dominate the fixed-horizon exit (edge is exit-driven)."""
    trail = ablation["trail"]
    fh = ablation["net_fixed_horizon_exit"]
    pf = trail["profit_factor"]
    cond1 = trail["expectancy_r"] > 0 and (pf == float("inf") or pf > 1.2)
    cond2 = trail["mar"] >= 1.5 * fh["mar"]
    cond3 = fh["expectancy_r"] <= 0.5 * trail["expectancy_r"]
    return cond1 and cond2 and cond3


_AXES = {"entry_n": [30, 40, 55], "trail_n": [10, 20, 30],
         "k_stop": [1.5, 2.0, 2.5], "atr_period": [14, 20]}
_CENTER = {"entry_n": 40, "trail_n": 20, "k_stop": 2.0, "atr_period": 14}


def _row_for(candles, funding, base_params, overrides: dict) -> dict:
    p = replace(base_params, **overrides)
    rs = [t.r_multiple for t in simulate_donchian(candles, p, funding)]
    row = _summary_row(rs)
    row["label"] = ",".join(f"{k}={v}" for k, v in overrides.items())
    return row


def local_param_plateau(candles, funding, base_params: TrendParams) -> dict:
    """One-axis-at-a-time (star) perturbations around the deployed center."""
    center = _row_for(candles, funding, base_params, dict(_CENTER))
    neighbors = []
    for axis, values in _AXES.items():
        for v in values:
            if v == _CENTER[axis]:
                continue
            ov = dict(_CENTER)
            ov[axis] = v
            neighbors.append(_row_for(candles, funding, base_params, ov))
    return {"center": center, "neighbors": neighbors}


def ps_pass(plateau: dict) -> bool:
    """Deployed point sits on a plateau, not a spike."""
    nb = plateau["neighbors"]
    if not nb:
        return False
    good = sum(1 for r in nb if r["expectancy_r"] > 0
               and (r["profit_factor"] == float("inf") or r["profit_factor"] > 1.2))
    near = sum(1 for r in nb if r["expectancy_r"] >= 0.75 * plateau["center"]["expectancy_r"])
    return good / len(nb) >= 0.6 and near >= 2


def param_diagnostic_grid(candles, funding, base_params: TrendParams) -> list[dict]:
    """Full cartesian sweep — REPORT-ONLY, never gated."""
    rows = []
    for en in _AXES["entry_n"]:
        for tn in _AXES["trail_n"]:
            for ks in _AXES["k_stop"]:
                for ap in _AXES["atr_period"]:
                    rows.append(_row_for(candles, funding, base_params,
                                         {"entry_n": en, "trail_n": tn,
                                          "k_stop": ks, "atr_period": ap}))
    return rows


def aggregate_econ_pass(row: dict) -> bool:
    pf = row["profit_factor"]
    return (row["expectancy_r"] >= ECON_BAR.expectancy_r
            and (pf == float("inf") or pf >= ECON_BAR.profit_factor)
            and row["mar"] >= ECON_BAR.mar_floor
            and abs(row["max_dd_r"]) <= ECON_BAR.max_dd_r)


_COST_TIERS = {
    "base":     dict(fee_rate=0.00045, slippage=0.0005, next_bar_open=False, stop_extra_slip=0.0),
    "moderate": dict(fee_rate=0.00075, slippage=0.0010, next_bar_open=True,  stop_extra_slip=0.0),
    "severe":   dict(fee_rate=0.0010,  slippage=0.0020, next_bar_open=True,  stop_extra_slip=0.0010),
}


def cost_stress(candles, funding, base_params: TrendParams) -> dict:
    out = {}
    for tier, cost in _COST_TIERS.items():
        p = replace(base_params, exit_mode="trail", **cost)
        rs = [t.r_multiple for t in simulate_donchian(candles, p, funding)]
        row = _summary_row(rs)
        if tier == "base":
            row["econ_pass"] = aggregate_econ_pass(row)
        if tier == "moderate":
            pf = row["profit_factor"]
            row["alive"] = (row["expectancy_r"] > 0
                            and (pf == float("inf") or pf > 1.0) and row["mar"] > 0)
        out[tier] = row
    return out


def _hist(values, edges) -> dict:
    out = {f"<{e}": 0 for e in edges}
    out[f">={edges[-1]}"] = 0
    for v in values:
        placed = False
        for e in edges:
            if v < e:
                out[f"<{e}"] += 1
                placed = True
                break
        if not placed:
            out[f">={edges[-1]}"] += 1
    return out


def trade_distribution(trades) -> dict:
    rs = [t.r_multiple for t in trades]
    n = len(rs)
    if n == 0:
        return {"n": 0, "td_extreme": False}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    total = sum(rs)
    payoff = (sum(wins) / len(wins)) / (abs(sum(losses)) / len(losses)) \
        if wins and losses else float("inf")
    ordered = sorted(rs, reverse=True)

    def exp_drop(k):
        rest = ordered[k:]
        return round(sum(rest) / len(rest), 4) if rest else 0.0

    top1 = ordered[0]
    top1_contribution = round(top1 / total, 4) if total > 0 else None
    exp_drop_top1 = exp_drop(1)
    td_extreme = bool((total > 0 and top1 / total > 0.5) or exp_drop_top1 < 0)
    return {
        "n": n,
        "win_rate": round(len(wins) / n, 4),
        "payoff_ratio": payoff if payoff == float("inf") else round(payoff, 4),
        "hold_hist": _hist([t.hold_bars for t in trades], [3, 6, 12, 24, 48]),
        "r_hist": _hist(rs, [-1.0, 0.0, 1.0, 2.0, 5.0]),
        "mae_hist": _hist([t.mae_r for t in trades], [0.25, 0.5, 0.75, 1.0]),
        "top1_contribution": top1_contribution,
        "exp_drop_top1": exp_drop_top1,
        "exp_drop_top5": exp_drop(5),
        "td_extreme": td_extreme,
    }


MIN_REGIME_EVENTS = 10  # per-regime trade count needed to judge RG


def _causal_atr_frac_series(candles, atr_period):
    """atr_frac at each bar using only bars up to and including that bar."""
    out = []
    for i in range(len(candles)):
        a = _atr_fn(candles[: i + 1], atr_period)
        out.append(a / candles[i].close if candles[i].close else 0.0)
    return out


def _vol_label(atr_fracs, i) -> str:
    """Tercile of atr_fracs[i] within the PAST window atr_fracs[:i+1]."""
    past = sorted(atr_fracs[: i + 1])
    if len(past) < 3:
        return "mid"
    rank = sum(1 for x in past if x < atr_fracs[i]) / len(past)
    return "low" if rank < 1 / 3 else ("high" if rank >= 2 / 3 else "mid")


def _rg_flag(bull_positive, total_positive, nonbull_total_r, nonbull_expectancy) -> bool:
    if total_positive <= 0:
        return False
    concentration = bull_positive / total_positive
    return concentration > 0.9 and nonbull_total_r < 0 and nonbull_expectancy < -0.05


def regime_breakdown(candles, trades, atr_period=14, sma_n=200) -> dict:
    closes = [c.close for c in candles]
    atr_fracs = _causal_atr_frac_series(candles, atr_period)
    trend = {"bull": [], "bear": [], "warmup": []}
    vol = {"low": [], "mid": [], "high": []}
    bull_positive = 0.0
    total_positive = 0.0
    nonbull_rs = []
    for t in trades:
        i = t.entry_index
        r = t.r_multiple
        if r > 0:
            total_positive += r
        if i + 1 >= sma_n:
            m = sma(closes[: i + 1], sma_n)
            label = "bull" if closes[i] > m else "bear"
        else:
            label = "warmup"
        trend[label].append(r)
        if label == "bull" and r > 0:
            bull_positive += r
        if label != "bull":
            nonbull_rs.append(r)
        vol[_vol_label(atr_fracs, i)].append(r)

    nb = summarize_r(nonbull_rs)
    rg_flag = _rg_flag(bull_positive, total_positive, nb.total_r, nb.expectancy_r)
    sufficient = all(len(v) >= MIN_REGIME_EVENTS for v in
                     (trend["bull"], trend["bear"])) and len(trades) >= MIN_REGIME_EVENTS
    return {
        "trend": {k: _summary_row(v) for k, v in trend.items()},
        "vol": {k: _summary_row(v) for k, v in vol.items()},
        "rg_flag": rg_flag,
        "regime_sufficient": sufficient,
    }


def nonoverlap_walk_forward(candles, funding, step_bars) -> dict:
    """N=4-style non-overlapping yearly windows (train=2y/test=1y) over the frozen
    grid; headline economics from the pooled test R (four aggregate gates)."""
    from tools.engine.swing_donchian import _BASE, _GRID
    train = step_bars * 2
    res = walk_forward(candles, funding, _GRID, train_bars=train,
                       test_bars=step_bars, step_bars=step_bars, base_params=_BASE)
    s = res.aggregated
    agg = {"n": s.trade_count, "expectancy_r": s.expectancy_r,
           "profit_factor": s.profit_factor, "max_dd_r": s.max_drawdown_r,
           "total_r": s.total_r, "mar": round(_mar(s), 4)}
    verdict = evaluate_econ(res.test_summaries, res.aggregated)
    return {"n_windows": len(res.test_summaries), "aggregate": agg,
            "robust_frac": verdict.metrics["robust_frac"],
            "wf_pass": aggregate_econ_pass(agg)}


@dataclass(frozen=True)
class Verdict:
    tier: str
    reasons: list


def revalidation_verdict(wf, ablation, plateau, cost, dist, regime) -> Verdict:
    structural = []
    if not wf["wf_pass"]:
        structural.append("non-overlap walk-forward fails aggregate ECON_BAR")
    if not cost["base"].get("econ_pass"):
        structural.append("base-cost run fails ECON_BAR")
    if not ea_pass(ablation):
        structural.append("exit ablation: trailing exit does not materially dominate fixed-horizon (no exit-driven edge)")
    if dist.get("td_extreme"):
        structural.append("extreme single-trade outlier dependence")
    if regime.get("rg_flag"):
        structural.append("profit concentrated in one bull leg, all else deeply negative")
    if structural:
        return Verdict("DOWNGRADE TO PARKED / NEEDS-FIX", structural)

    nonstructural = []
    if not cost["moderate"].get("alive"):
        nonstructural.append("moderate-cost run not economically alive")
    if not ps_pass(plateau):
        nonstructural.append("local parameter plateau weak")
    if wf["robust_frac"] < 0.6:
        nonstructural.append(f"N={wf['n_windows']} robust_frac {wf['robust_frac']} < 0.60 (quantized; see Slice-2)")
    if not regime.get("regime_sufficient"):
        nonstructural.append("insufficient per-regime events to judge concentration")
    if nonstructural:
        return Verdict("INCONCLUSIVE / PAPER-SUSPENDED", nonstructural)
    return Verdict("REAFFIRM PAPER", ["all structural + support criteria met"])


def _g(x):
    return "-" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def render_result(symbol, interval, bars, data_sha, asof, wf, gross,
                  ablation, plateau, cost, dist, regime, verdict) -> str:
    L = []
    L.append(f"# BTC Donchian Revalidation — {symbol} {interval}\n")
    L.append(f"## Verdict: {verdict.tier}\n")
    L.append(f"- asof: {asof}")
    L.append(f"- bars: {bars}  data_sha: {data_sha}")
    L.append("- gates: ECON_BAR (PF>=1.2/exp>=0.05R/MAR>=0.5/|maxDD|<=30R/robust>=0.60)\n")
    L.append("## Reasons\n")
    L.extend(f"- {r}" for r in verdict.reasons)
    L.append("\n## Headline non-overlap walk-forward")
    a = wf["aggregate"]
    L.append(f"- windows: {wf['n_windows']}  wf_pass: {wf['wf_pass']}")
    L.append(f"- expectancy_r {a['expectancy_r']}  PF {a['profit_factor']}  "
             f"MAR {a['mar']}  maxDD {a['max_dd_r']}R  robust_frac {wf['robust_frac']}")
    L.append("\n## Exit ablation (entry fixed: Donchian n=40)")
    L.append(f"- gross_h12_probe: n={gross['n']} z={_g(gross['z'])} (edge-search reproduction; expect |z|<2)")
    L.append("| arm | n | expectancy_r | PF | MAR | maxDD_R |")
    L.append("|---|---|---|---|---|---|")
    for name in ("net_fixed_horizon_exit", "stop_only", "trail"):
        r = ablation[name]
        L.append(f"| {name} | {r['n']} | {r['expectancy_r']} | {r['profit_factor']} | {r['mar']} | {r['max_dd_r']} |")
    L.append("\n## Local parameter plateau (one-axis star around 40/20/2.0/14)")
    c = plateau["center"]
    L.append(f"- center expectancy_r {c['expectancy_r']} PF {c['profit_factor']} MAR {c['mar']}")
    for r in plateau["neighbors"]:
        L.append(f"  - {r['label']}: exp {r['expectancy_r']} PF {r['profit_factor']} MAR {r['mar']}")
    L.append("\n## Cost / fill stress")
    L.append("| tier | n | expectancy_r | PF | MAR | maxDD_R | gate |")
    L.append("|---|---|---|---|---|---|---|")
    L.append(f"| base | {cost['base']['n']} | {cost['base']['expectancy_r']} | {cost['base']['profit_factor']} | {cost['base']['mar']} | {cost['base']['max_dd_r']} | econ_pass={cost['base']['econ_pass']} |")
    L.append(f"| moderate | {cost['moderate']['n']} | {cost['moderate']['expectancy_r']} | {cost['moderate']['profit_factor']} | {cost['moderate']['mar']} | {cost['moderate']['max_dd_r']} | alive={cost['moderate']['alive']} |")
    L.append(f"| severe | {cost['severe']['n']} | {cost['severe']['expectancy_r']} | {cost['severe']['profit_factor']} | {cost['severe']['mar']} | {cost['severe']['max_dd_r']} | report-only |")
    L.append("\n## Trade distribution")
    L.append(f"- n {dist['n']} win_rate {dist.get('win_rate')} payoff {dist.get('payoff_ratio')}")
    L.append(f"- top1_contribution {dist.get('top1_contribution')} exp_drop_top1 {dist.get('exp_drop_top1')} exp_drop_top5 {dist.get('exp_drop_top5')} td_extreme {dist['td_extreme']}")
    L.append(f"- hold_hist {dist.get('hold_hist')}")
    L.append(f"- r_hist {dist.get('r_hist')}")
    L.append("\n## Regime breakdown (point-in-time labels)")
    for k, r in regime["trend"].items():
        L.append(f"- trend/{k}: n {r['n']} exp {r['expectancy_r']} PF {r['profit_factor']} total_r {r['total_r']}")
    for k, r in regime["vol"].items():
        L.append(f"- vol/{k}: n {r['n']} exp {r['expectancy_r']} PF {r['profit_factor']} total_r {r['total_r']}")
    L.append(f"- rg_flag {regime['rg_flag']}  regime_sufficient {regime['regime_sufficient']}")
    L.append("\n## Honest caveat\n")
    L.append("Single-asset BTC, paper-only. REAFFIRM means keep on paper, never go live. "
             "N=4 windows give a quantized robust_frac; Slice-2's overlapping estimate is the finer read. "
             "Point-in-time regime labels still describe one realised 6.5y BTC path.")
    return "\n".join(L) + "\n"
