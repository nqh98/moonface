"""3-stage MTF evaluation, reusing the frozen edge-search gate.

Identical stages and floors to research.edge_search, but entries come from the
MTF combiner (gen closure) instead of a single price family. The closure
re-derives the HTF from whatever candle slice it is handed, so every
walk-forward window resamples its own HTF -- point-in-time, no leakage across
windows.

Stage 1  gross pre-screen : Stouffer Z on gross per-event forward R  (|Z|>=2.0)
Stage 2  OOS deflated SR  : net per-trade R, DSR vs the full grid     (>=0.95)
Stage 3  econ walk-forward: frozen rolling windows, evaluate_econ      (ECON_BAR)
A cell failing any stage is closed (kill rule)."""
from __future__ import annotations

from moonface.core.metrics import (_kurtosis, _sharpe, _skew,
                                          deflated_sharpe, single_trade_r,
                                          summarize_r)
from moonface.research.drift_screen import event_outcome
from moonface.kernel.econ import ECON_BAR, evaluate_econ
from moonface.research.mtf.combine import mtf_entries
from moonface.research.mtf.grid import BASE_TF, BIAS_FNS, TRIGGER_FNS, MtfCell
from moonface.features.oi_features import nonoverlap
from moonface.research.resrev import mean_z

Z_FLOOR = 2.0
DSR_FLOOR = 0.95
MIN_EVENTS = 30


def cell_gen(cell: MtfCell):
    """A closure mapping a candle slice -> MTF L/S entries for this cell."""
    bias_fn = BIAS_FNS[cell.bias_fn]
    trigger_fn = TRIGGER_FNS[cell.trigger_fn]

    def gen(candles):
        return mtf_entries(candles, BASE_TF, cell.htf, bias_fn,
                           cell.bias_params, trigger_fn, cell.trigger_params)
    return gen


def _gross_event_rs(candles, gen, h, atr_period):
    rs = []
    for i, side in nonoverlap(gen(candles), h):
        out = event_outcome(candles, i, side, h, atr_period)
        if out is not None:
            rs.append(out[0])
    return rs


def prescreen(candles, cell: MtfCell) -> dict:
    rs = _gross_event_rs(candles, cell_gen(cell), cell.h,
                         cell.exit_params["atr_period"])
    n = len(rs)
    mean, z = mean_z(rs)
    sign_rate = (sum(1 for r in rs if r > 0) / n) if n else 0.0
    passed = n >= MIN_EVENTS and abs(z) >= Z_FLOOR
    reason = (f"n={n} z={z:.2f} mean_ret_r={mean:.4f}"
              + ("" if passed else f" (need n>={MIN_EVENTS}, |z|>={Z_FLOOR})"))
    return {"n": n, "mean_ret_r": mean, "z": z, "sign_rate": sign_rate,
            "passed": passed, "reason": reason}


def iter_trades(candles, cell: MtfCell):
    """Yield (entry_idx, side, net_r) for each non-overlapping entry. The one
    place that decides how a cell's trades resolve: the structural regime_flip
    exit routes through the mtf-local resolver (it needs the HTF bias), every
    frozen exit through single_trade_r. The HTF bias is computed once per slice."""
    from moonface.research.mtf.regime_exit import bias_for, regime_flip_r
    entries = nonoverlap(cell_gen(cell)(candles), cell.h)
    bias = bias_for(candles, cell) if cell.exit_name == "regime_flip" else None
    for i, side in entries:
        if bias is not None:
            res = regime_flip_r(candles, i, side, cell.exit_params, bias)
        else:
            res = single_trade_r(candles, i, side, cell.exit_name, cell.exit_params)
        if res is not None:
            yield i, side, res[0]


def net_trade_rs(candles, cell: MtfCell) -> list[float]:
    return [r for _, _, r in iter_trades(candles, cell)]


def oos_dsr(candles, cell: MtfCell, trial_srs, n_trials) -> dict:
    rs = net_trade_rs(candles, cell)
    n = len(rs)
    sr = _sharpe(rs) if n >= 2 else 0.0
    dsr = (deflated_sharpe(sr, n, _skew(rs), _kurtosis(rs), trial_srs, n_trials)
           if n >= MIN_EVENTS else 0.0)
    passed = dsr >= DSR_FLOOR
    reason = (f"n={n} sharpe={sr:.3f} dsr={dsr:.3f}"
              + ("" if passed else f" (need n>={MIN_EVENTS}, dsr>={DSR_FLOOR})"))
    return {"n": n, "sharpe": sr, "dsr": dsr, "passed": passed, "reason": reason}


def econ_walk_forward(candles, cell: MtfCell) -> dict:
    summaries, agg_rs = [], []
    start, n = 0, len(candles)
    while start + cell.test_bars <= n:
        window = candles[start:start + cell.test_bars]
        rs = [r for _, _, r in iter_trades(window, cell)]
        summaries.append(summarize_r(rs))
        agg_rs.extend(rs)
        start += cell.step_bars
    verdict = evaluate_econ(summaries, summarize_r(agg_rs), ECON_BAR)
    return {"n_windows": len(summaries), "passed": verdict.passed,
            "reasons": list(verdict.reasons), "metrics": dict(verdict.metrics)}


def _cell_oos_sharpe(cell: MtfCell, train_oos) -> float:
    rs = net_trade_rs(train_oos, cell)
    return _sharpe(rs) if len(rs) >= 2 else 0.0


def run_cell(cell: MtfCell, train_oos, full, trial_srs, n_trials) -> dict:
    base = {"label": cell.label, "htf": cell.htf, "trigger": cell.trigger_fn,
            "exit": cell.exit_name, "stage1": None, "stage2": None,
            "stage3": None, "verdict": "negative"}
    s1 = prescreen(train_oos, cell)
    base["stage1"] = s1
    if not s1["passed"]:
        return base
    s2 = oos_dsr(train_oos, cell, trial_srs, n_trials)
    base["stage2"] = s2
    if not s2["passed"]:
        return base
    s3 = econ_walk_forward(full, cell)
    base["stage3"] = s3
    base["verdict"] = "edge" if s3["passed"] else "negative"
    return base


def search(cells: list[MtfCell], train_oos, full) -> list[dict]:
    """Run every cell. trial_srs (full grid's OOS Sharpe) is computed once so DSR
    deflates against the true trial count."""
    trial_srs = [_cell_oos_sharpe(c, train_oos) for c in cells]
    rows = [run_cell(c, train_oos, full, trial_srs, len(cells)) for c in cells]
    rows.sort(key=lambda r: (r["stage2"]["dsr"] if r["stage2"] else float("-inf")),
              reverse=True)
    return rows


def run_cell_diagnostic(cell: MtfCell, train_oos, full, trial_srs,
                        n_trials) -> dict:
    """Like run_cell but ALWAYS computes all three stages (no early kill), so the
    economic picture (PF/MAR/DD/robust) is visible for every cell regardless of
    the academic DSR gate. The strict verdict still requires all three to pass;
    econ_pass reports the repo's deployable ECON_BAR alone."""
    s1 = prescreen(train_oos, cell)
    s2 = oos_dsr(train_oos, cell, trial_srs, n_trials)
    s3 = econ_walk_forward(full, cell)
    strict = s1["passed"] and s2["passed"] and s3["passed"]
    return {"label": cell.label, "htf": cell.htf, "trigger": cell.trigger_fn,
            "exit": cell.exit_name, "stage1": s1, "stage2": s2, "stage3": s3,
            "econ_pass": s3["passed"],
            "verdict": "edge" if strict else "negative"}


def search_diagnostic(cells: list[MtfCell], train_oos, full) -> list[dict]:
    """Run every cell through all three stages unconditionally. Sorted by econ
    MAR (the deployable signal) then DSR, so the most economically interesting
    cells surface first even when none clears the academic gate."""
    trial_srs = [_cell_oos_sharpe(c, train_oos) for c in cells]
    rows = [run_cell_diagnostic(c, train_oos, full, trial_srs, len(cells))
            for c in cells]
    rows.sort(key=lambda r: (r["stage3"]["metrics"].get("mar", 0.0),
                             r["stage2"]["dsr"]), reverse=True)
    return rows


def to_leaderboard(rows) -> list[dict]:
    out = []
    for r in rows:
        s1, s2, s3 = r["stage1"], r["stage2"], r["stage3"]
        m = (s3 or {}).get("metrics", {}) if s3 else {}
        out.append({
            "label": r["label"],
            "n1": s1["n"] if s1 else None, "z": s1["z"] if s1 else None,
            "dsr": s2["dsr"] if s2 else None,
            "econ_pf": m.get("profit_factor"), "econ_mar": m.get("mar"),
            "econ_dd": m.get("max_dd_r"), "robust_frac": m.get("robust_frac"),
            "verdict": r["verdict"]})
    return out


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def render_result(rows, asof, data_sha, n_cells) -> str:
    any_edge = any(r["verdict"] == "edge" for r in rows)
    overall = "EDGE FOUND (promote to paper — NOT live)" if any_edge else "NEGATIVE"
    caveat = ("A NEGATIVE is the expected, valid outcome given the program's long "
              "history of closed domains. Single-asset BTC evidence — any EDGE is "
              "paper-only and needs cross-asset transfer confirmation before live "
              "consideration. The MTF lever targets path drawdown specifically: it "
              "trades only with the HTF trend to cut the adverse excursions that "
              "killed single-timeframe breakouts.")
    head = ("# MTF Confluence Edge Search — BTC 15m trigger + HTF bias\n\n"
            f"## Verdict: {overall}\n\n"
            f"- asof: {asof}\n- data_sha: {data_sha}\n"
            f"- base_tf: {BASE_TF}\n"
            f"- gate: |Z|>={Z_FLOOR} -> DSR>={DSR_FLOOR} (n_trials={n_cells}) "
            "-> ECON_BAR(PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60)\n\n"
            "| cell | n | z | dsr | pf | mar | ddR | robust | verdict |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for lb in to_leaderboard(rows):
        lines.append(
            f"| {lb['label']} | {lb['n1']} | {_f(lb['z'])} | {_f(lb['dsr'])} | "
            f"{_f(lb['econ_pf'])} | {_f(lb['econ_mar'])} | {_f(lb['econ_dd'])} | "
            f"{_f(lb['robust_frac'])} | {lb['verdict']} |")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"


def render_diagnostic(rows, asof, data_sha, n_cells) -> str:
    """Full economic table for every cell (econ always computed). Leads on the
    deployable ECON_BAR, not the academic DSR gate: a cell that clears ECON_BAR
    is a paper candidate even if DSR < 0.95."""
    strict = [r for r in rows if r["verdict"] == "edge"]
    econ = [r for r in rows if r["econ_pass"]]
    if strict:
        overall = "EDGE (clears DSR + ECON_BAR — paper candidate)"
    elif econ:
        overall = (f"ECON-POSITIVE ({len(econ)} cell(s) clear ECON_BAR but not "
                   "DSR — practical paper candidate, academically underpowered)")
    else:
        overall = "NEGATIVE (no cell clears the deployable ECON_BAR)"
    head = ("# MTF Confluence — BTC 15m entry + HTF bias "
            "(momentum vs counter-trend)\n\n"
            f"## Verdict: {overall}\n\n"
            f"- asof: {asof}\n- data_sha: {data_sha}\n- base_tf: {BASE_TF}\n"
            f"- diagnostic: econ walk-forward computed for ALL {n_cells} cells "
            "(not DSR-gated)\n"
            "- ECON_BAR: PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60\n"
            f"- DSR gate (academic, n_trials={n_cells}): >=0.95\n\n"
            "| cell | n | z | dsr | pf | mar | ddR | robust | econ | strict |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for lb, r in zip(to_leaderboard(rows), rows):
        lines.append(
            f"| {lb['label']} | {lb['n1']} | {_f(lb['z'])} | {_f(lb['dsr'])} | "
            f"{_f(lb['econ_pf'])} | {_f(lb['econ_mar'])} | {_f(lb['econ_dd'])} | "
            f"{_f(lb['robust_frac'])} | {'PASS' if r['econ_pass'] else '-'} | "
            f"{r['verdict']} |")
    note = ("Momentum triggers (donchian_break/bb_breakout) buy strength; "
            "counter-trend triggers (rsi_reversion/ma_reclaim) buy weakness "
            "inside the HTF trend (buy-the-dip / sell-the-rip). Compare their "
            "drawdown (ddR) and MAR columns to see whether better entry price "
            "cuts the path drawdown. Single-asset BTC; any paper candidate needs "
            "cross-asset transfer before live consideration.")
    return head + "\n".join(lines) + f"\n\n## Reading this\n\n{note}\n"
