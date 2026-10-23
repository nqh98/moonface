# src/moonface/research/edge_search.py
"""Pre-registered 3-stage price-only edge search (single asset, one timeframe).

Stage 1  cost-first gross pre-screen : Stouffer Z on gross per-event forward R.
Stage 2  OOS deflated Sharpe         : net per-trade R, DSR vs the frozen grid.
Stage 3  economic-bar walk-forward   : frozen-param rolling test, evaluate_econ.

A cell failing any stage is closed (kill rule). Params are frozen per cell; no
per-window param search. Design: docs/research-log/specs/2026-06-19-dual-timeframe
-price-edge-search-design.md. Pure module — network IO lives in tools/."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.metrics import (deflated_sharpe, single_trade_r,
                                          summarize_r, _sharpe, _skew, _kurtosis)
from moonface.research.drift_screen import event_outcome
from moonface.kernel.econ import ECON_BAR, evaluate_econ
from moonface.research.entries import PRICE_FAMILIES
from moonface.features.oi_features import nonoverlap
from moonface.research.resrev import mean_z

Z_FLOOR = 2.0          # |Stouffer Z| on gross per-event R (frozen)
DSR_FLOOR = 0.95       # deflated Sharpe gate (frozen)
MIN_EVENTS = 30        # min non-overlapping events for any stage to be meaningful
TOTAL_CELLS = 9        # 4 swing + 5 day; n_trials for DSR (frozen, both agents)


def _gross_event_rs(candles, family, params, h, atr_period):
    """Gross forward R per non-overlapping event (no costs); used by stage 1."""
    events = nonoverlap(PRICE_FAMILIES[family](candles, params), h)
    rs = []
    for i, side in events:
        out = event_outcome(candles, i, side, h, atr_period)
        if out is not None:
            rs.append(out[0])  # ret_r
    return rs


def prescreen(candles, family, params, h, atr_period) -> dict:
    """Stage 1. Kill a cell whose gross drift is indistinguishable from a coin
    flip. Reusing event_outcome's gross ret_r means cost cannot rescue what is
    already null gross — the cheap filter."""
    rs = _gross_event_rs(candles, family, params, h, atr_period)
    n = len(rs)
    mean, z = mean_z(rs)
    sign_rate = (sum(1 for r in rs if r > 0) / n) if n else 0.0
    passed = n >= MIN_EVENTS and abs(z) >= Z_FLOOR
    reason = (f"n={n} z={z:.2f} mean_ret_r={mean:.4f}"
              + ("" if passed else f" (need n>={MIN_EVENTS}, |z|>={Z_FLOOR})"))
    return {"n": n, "mean_ret_r": mean, "z": z, "sign_rate": sign_rate,
            "passed": passed, "reason": reason}


def net_trade_rs(candles, family, params, exit_name, exit_params, h) -> list[float]:
    """Net per-trade R (costs applied by single_trade_r) for each non-overlapping
    entry resolved through the frozen exit."""
    events = nonoverlap(PRICE_FAMILIES[family](candles, params), h)
    rs = []
    for i, side in events:
        res = single_trade_r(candles, i, side, exit_name, exit_params)
        if res is not None:
            rs.append(res[0])
    return rs


def oos_dsr(candles, family, params, exit_name, exit_params, h,
            trial_srs, n_trials=TOTAL_CELLS) -> dict:
    """Stage 2. Per-trade Sharpe deflated against the full registered grid."""
    rs = net_trade_rs(candles, family, params, exit_name, exit_params, h)
    n = len(rs)
    sr = _sharpe(rs) if n >= 2 else 0.0
    dsr = (deflated_sharpe(sr, n, _skew(rs), _kurtosis(rs), trial_srs, n_trials)
           if n >= MIN_EVENTS else 0.0)
    passed = dsr >= DSR_FLOOR
    reason = (f"n={n} sharpe={sr:.3f} dsr={dsr:.3f}"
              + ("" if passed else f" (need n>={MIN_EVENTS}, dsr>={DSR_FLOOR})"))
    return {"n": n, "sharpe": sr, "dsr": dsr, "passed": passed, "reason": reason}


def _window_trade_rs(window, family, params, exit_name, exit_params, h):
    return net_trade_rs(window, family, params, exit_name, exit_params, h)


def econ_walk_forward(candles, family, params, exit_name, exit_params, h,
                      test_bars, step_bars) -> dict:
    """Stage 3. Roll fixed-length test windows; run the FROZEN params on each;
    aggregate test R and apply the economic bar. Window robustness = fraction of
    windows that are individually PF>1 and expectancy>0 (evaluate_econ)."""
    summaries = []
    agg_rs: list[float] = []
    start = 0
    n = len(candles)
    while start + test_bars <= n:
        window = candles[start:start + test_bars]
        rs = _window_trade_rs(window, family, params, exit_name, exit_params, h)
        summaries.append(summarize_r(rs))
        agg_rs.extend(rs)
        start += step_bars
    verdict = evaluate_econ(summaries, summarize_r(agg_rs), ECON_BAR)
    return {"n_windows": len(summaries), "passed": verdict.passed,
            "reasons": list(verdict.reasons), "metrics": dict(verdict.metrics)}


@dataclass(frozen=True)
class Cell:
    label: str
    family: str
    params: dict
    exit_name: str
    exit_params: dict
    h: int
    test_bars: int
    step_bars: int
    is_retest: bool


def run_cell(cell, train_oos_candles, full_candles, trial_srs,
             n_trials=TOTAL_CELLS) -> dict:
    base = {"label": cell.label, "family": cell.family,
            "is_retest": cell.is_retest, "stage1": None, "stage2": None,
            "stage3": None, "verdict": "negative"}
    s1 = prescreen(train_oos_candles, cell.family, cell.params, cell.h,
                   cell.exit_params["atr_period"])
    base["stage1"] = s1
    if not s1["passed"]:
        return base
    s2 = oos_dsr(train_oos_candles, cell.family, cell.params, cell.exit_name,
                 cell.exit_params, cell.h, trial_srs, n_trials)
    base["stage2"] = s2
    if not s2["passed"]:
        return base
    s3 = econ_walk_forward(full_candles, cell.family, cell.params, cell.exit_name,
                           cell.exit_params, cell.h, cell.test_bars, cell.step_bars)
    base["stage3"] = s3
    base["verdict"] = "edge" if s3["passed"] else "negative"
    return base


def _cell_oos_sharpe(cell, train_oos_candles) -> float:
    rs = net_trade_rs(train_oos_candles, cell.family, cell.params,
                      cell.exit_name, cell.exit_params, cell.h)
    return _sharpe(rs) if len(rs) >= 2 else 0.0


def search(cells, train_oos_candles, full_candles) -> list[dict]:
    """Run every registered cell. trial_srs is the full grid's per-cell OOS
    Sharpe (computed once, before deflation) so DSR sees the true trial count."""
    trial_srs = [_cell_oos_sharpe(c, train_oos_candles) for c in cells]
    rows = [run_cell(c, train_oos_candles, full_candles, trial_srs, TOTAL_CELLS)
            for c in cells]
    rows.sort(key=lambda r: (r["stage2"]["dsr"] if r["stage2"] else float("-inf")),
              reverse=True)
    return rows


def to_leaderboard(rows) -> list[dict]:
    out = []
    for r in rows:
        s1, s2, s3 = r["stage1"], r["stage2"], r["stage3"]
        m = (s3 or {}).get("metrics", {}) if s3 else {}
        out.append({
            "label": r["label"], "family": r["family"],
            "is_retest": r["is_retest"],
            "n1": s1["n"] if s1 else None, "z": s1["z"] if s1 else None,
            "dsr": s2["dsr"] if s2 else None,
            "econ_pf": m.get("profit_factor"), "econ_mar": m.get("mar"),
            "econ_dd": m.get("max_dd_r"), "robust_frac": m.get("robust_frac"),
            "verdict": r["verdict"]})
    return out


def render_result(timeframe, rows, asof, data_sha) -> str:
    any_edge = any(r["verdict"] == "edge" for r in rows)
    overall = "EDGE FOUND (promote to paper — NOT live)" if any_edge else "NEGATIVE"
    caveat = ("A NEGATIVE is the expected, valid outcome given the program's "
              "58 closed domains; it is cheaper to learn here than with live capital. "
              "Single-asset BTC evidence — any EDGE is paper-only and needs cross-asset "
              "transfer confirmation before live consideration.")
    head = (f"# Price-Only Edge Search — BTC {timeframe}\n\n"
            f"## Verdict: {overall}\n\n"
            f"- asof: {asof}\n- data_sha: {data_sha}\n"
            f"- gate: Z_FLOOR={Z_FLOOR} -> DSR_FLOOR={DSR_FLOOR} "
            f"(n_trials={TOTAL_CELLS}) -> economic bar\n\n"
            "| cell | retest | n | z | dsr | pf | mar | ddR | robust | verdict |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for lb in to_leaderboard(rows):
        lines.append(
            f"| {lb['label']} | {'Y' if lb['is_retest'] else 'N'} | {lb['n1']} | "
            f"{_f(lb['z'])} | {_f(lb['dsr'])} | {_f(lb['econ_pf'])} | "
            f"{_f(lb['econ_mar'])} | {_f(lb['econ_dd'])} | "
            f"{_f(lb['robust_frac'])} | {lb['verdict']} |")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))
