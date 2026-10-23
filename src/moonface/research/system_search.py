"""System-level strategy search orchestrator.

Differs from edge_search in three frozen ways (see the design doc):
1. Gross fixed-horizon drift is a DIAGNOSTIC ONLY — it never short-circuits a
   cell (edge_search.run_cell kills on stage 1; this does not).
2. A robustness battery runs after DSR + ECON_BAR; a survivor that fails any
   battery check is `inconclusive`, never `edge`.
3. The plateau rule finalizes `edge`: a cell is `edge` only if its group's
   center param AND >=1 neighbor cleared stage 3 (ECON_BAR).

n_trials for DSR is the pooled total cell count across ALL timeframes."""
from __future__ import annotations

from moonface.core.metrics import _sharpe
from moonface.research.edge_search import (econ_walk_forward, net_trade_rs,
                                           oos_dsr, prescreen)
from moonface.research.system_battery import run_battery


def run_system_cell(cell, train_oos, full, trial_srs, n_trials) -> dict:
    row = {"label": cell.label, "family": cell.family,
           "timeframe": cell.timeframe, "group": cell.group,
           "is_retest": cell.is_retest, "swept": cell.swept,
           "gross": None, "stage2": None, "stage3": None, "battery": None,
           "plateau": None, "verdict": "negative"}
    # Stage 0 (diagnostic only — NEVER gates):
    row["gross"] = prescreen(train_oos, cell.family, cell.params, cell.h,
                             cell.exit_params["atr_period"])
    # Stage 1 — DSR on OOS system returns (pooled n_trials):
    s2 = oos_dsr(train_oos, cell.family, cell.params, cell.exit_name,
                 cell.exit_params, cell.h, trial_srs, n_trials)
    row["stage2"] = s2
    if not s2["passed"]:
        return row
    # Stage 2 — ECON_BAR walk-forward (opens the holdout via `full`):
    s3 = econ_walk_forward(full, cell.family, cell.params, cell.exit_name,
                           cell.exit_params, cell.h, cell.test_bars, cell.step_bars)
    row["stage3"] = s3
    if not s3["passed"]:
        return row
    # Stage 3 — robustness battery:
    battery = run_battery(train_oos, full, cell.family, cell.params,
                          cell.exit_name, cell.exit_params, cell.h)
    row["battery"] = battery
    # plateau decided later; until then, a battery-clean survivor is edge_pending.
    row["verdict"] = "edge_pending" if battery["passed"] else "inconclusive"
    return row


def finalize_plateau(rows) -> list[dict]:
    """A group passes the plateau rule if its CENTER swept point and >=1 adjacent
    point both cleared stage 3. Only then does an edge_pending row become edge."""
    by_group: dict[str, list[dict]] = {}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
    plateau_groups: set[str] = set()
    for group, members in by_group.items():
        ordered = sorted(members, key=lambda r: r["swept"])
        passed = [bool(r.get("stage3") and r["stage3"]["passed"]) for r in ordered]
        center = len(ordered) // 2
        neighbors = [center - 1, center + 1]
        if passed[center] and any(0 <= j < len(passed) and passed[j] for j in neighbors):
            plateau_groups.add(group)
    for r in rows:
        ok = r["group"] in plateau_groups
        r["plateau"] = ok
        if r["verdict"] == "edge_pending":
            r["verdict"] = "edge" if ok else "inconclusive"
    return rows


def _cell_oos_sharpe(cell, train_oos) -> float:
    rs = net_trade_rs(train_oos, cell.family, cell.params, cell.exit_name,
                      cell.exit_params, cell.h)
    return _sharpe(rs) if len(rs) >= 2 else 0.0


def search_system(entries) -> list[dict]:
    """entries: list of (cell, train_oos, full). Pooled n_trials = len(entries);
    trial_srs = each cell's OOS Sharpe (each on its own timeframe's train_oos)."""
    n_trials = len(entries)
    trial_srs = [_cell_oos_sharpe(cell, train_oos) for cell, train_oos, _ in entries]
    rows = [run_system_cell(cell, train_oos, full, trial_srs, n_trials)
            for cell, train_oos, full in entries]
    rows = finalize_plateau(rows)
    rows.sort(key=lambda r: (r["stage2"]["dsr"] if r["stage2"] else float("-inf")),
              reverse=True)
    return rows


def to_leaderboard(rows) -> list[dict]:
    out = []
    for r in rows:
        s3m = (r["stage3"] or {}).get("metrics", {}) if r["stage3"] else {}
        b = (r["battery"] or {}).get("checks", {}) if r["battery"] else {}
        out.append({
            "label": r["label"], "timeframe": r["timeframe"],
            "family": r["family"], "is_retest": r["is_retest"],
            "gross_z": (r["gross"] or {}).get("z"),
            "dsr": (r["stage2"] or {}).get("dsr"),
            "econ_pf": s3m.get("profit_factor"), "econ_mar": s3m.get("mar"),
            "econ_dd": s3m.get("max_dd_r"), "robust_frac": s3m.get("robust_frac"),
            "battery_ok": (r["battery"] or {}).get("passed"),
            "battery_fail": [k for k, v in b.items() if not v["passed"]],
            "plateau": r["plateau"], "verdict": r["verdict"]})
    return out


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def render_result(rows, asof, data_shas: dict) -> str:
    any_edge = any(r["verdict"] == "edge" for r in rows)
    overall = "EDGE FOUND (paper candidate — NOT live)" if any_edge else "NEGATIVE"
    shas = ", ".join(f"{tf}={s}" for tf, s in sorted(data_shas.items()))
    head = (f"# BTC System-Level Strategy Search\n\n## Verdict: {overall}\n\n"
            f"- asof: {asof}\n- data_sha: {shas}\n"
            f"- n_trials (pooled): {len(rows)}\n"
            f"- gate: gross(diagnostic) -> DSR>=0.95 -> ECON_BAR -> battery -> plateau\n\n"
            "| cell | tf | retest | gross_z | dsr | pf | mar | ddR | robust | "
            "battery | plateau | verdict |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for lb in to_leaderboard(rows):
        bf = ",".join(lb["battery_fail"]) if lb["battery_fail"] else "-"
        batt = ("-" if lb["battery_ok"] is None
                else ("OK" if lb["battery_ok"] else f"FAIL[{bf}]"))
        lines.append(
            f"| {lb['label']} | {lb['timeframe']} | "
            f"{'Y' if lb['is_retest'] else 'N'} | {_f(lb['gross_z'])} | "
            f"{_f(lb['dsr'])} | {_f(lb['econ_pf'])} | {_f(lb['econ_mar'])} | "
            f"{_f(lb['econ_dd'])} | {_f(lb['robust_frac'])} | {batt} | "
            f"{'-' if lb['plateau'] is None else ('Y' if lb['plateau'] else 'N')} | "
            f"{lb['verdict']} |")
    caveat = ("A NEGATIVE is the expected, valid outcome given the program's 58 "
              "closed domains. Any EDGE is a single-asset BTC PAPER candidate only — "
              "it does NOT authorize live capital and must later get its own frozen "
              "paper-forward protocol. The frozen 4h Donchian Slice-3 strategy is "
              "untouched by this lane.")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"
