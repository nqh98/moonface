# src/moonface/research/orderflow_runner.py
"""Dedicated runner for the orderflow_microstructure domain (spec 2026-07-02).

Reuses Store (registration + one-touch lockbox) and FencedBundle (one-touch
tail), but drives the entry-pair dominance ladder + walk-forward itself: the
generic runner.run cannot express the donchian_break control-dominance gate.
The generic runner skips any domain whose config.runner is neither None nor
'generic' (the guard in runner.run)."""
from __future__ import annotations

import json
from pathlib import Path

from moonface.core.metrics import deflated_sharpe
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.kernel.lockbox import FencedBundle
from moonface.research.orderflow import (control_for, evaluate_dominant,
                                        lockbox_dominant, orderflow_specs,
                                        stage1_of, stage2_of, stage4_of)
from moonface.research.orderflow_wf import stage35_of, walk_forward
from moonface.kernel.spec import spec_from_json, spec_hash
from moonface.kernel.store import Store

ORDERFLOW_DOMAIN = "orderflow_microstructure"
ORDERFLOW_START_MS = 1_598_918_400_000   # 2020-09-01 UTC (Binance Vision metrics availability)
LOCKBOX_FRACTION = 0.2


def register(store: Store, now_ms: int) -> None:
    """Freeze the window + fence and insert the 10-spec grid. Idempotent."""
    fence_ts = now_ms - int((now_ms - ORDERFLOW_START_MS) * LOCKBOX_FRACTION)
    if store.domain(ORDERFLOW_DOMAIN, 1) is None:
        store.register_domain(ORDERFLOW_DOMAIN, 1, "active",
                              {"runner": "orderflow"}, ORDERFLOW_START_MS,
                              now_ms, fence_ts)
        store.insert_grid(ORDERFLOW_DOMAIN, 1, orderflow_specs())


def run_domain(store: Store, loader, out_root: Path) -> str:
    d = store.domain(ORDERFLOW_DOMAIN, 1)
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(ORDERFLOW_DOMAIN, 1)]
    grid_size = len(specs)            # == N_TRIALS == 10
    fenced: dict[str, FencedBundle] = {}

    def fb_for(spec):
        key = json.dumps(spec.asset, sort_keys=True)
        if key not in fenced:
            fenced[key] = FencedBundle(
                loader(spec.asset, d["start_ms"], d["end_ms"]), d["fence_ts"])
        return fenced[key]

    # Pass 1: stages 1, 2, 3.5 per spec (with control dominance).
    rows: list[dict] = []
    for spec in specs:
        h = spec_hash(spec)
        fb = fb_for(spec)
        research = fb.research()
        ctrl = control_for(spec)
        m = evaluate_dominant(spec, ctrl, research, SCREEN_FRACTION)
        rows.append({"spec_hash": h, "spec": spec, "m": m, "wf": None,
                     "stage": "research"})
        if not stage1_of(m):
            rows[-1]["stage"] = "rejected_stage1"
            continue
        if not stage2_of(m):
            rows[-1]["stage"] = "rejected_stage2"
            continue
        wf = walk_forward(spec, research, ctrl)
        rows[-1]["wf"] = wf
        if not stage35_of(wf):
            rows[-1]["stage"] = "rejected_wf"
            continue
        rows[-1]["stage"] = "wf_pass"

    # Pass 2: DSR (stage 3) across survivors; trial variance from ALL specs.
    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    dsr: dict[str, float] = {}
    for r in rows:
        if r["stage"] != "wf_pass":
            continue
        m = r["m"]
        value = deflated_sharpe(m["research_sharpe"], m["research_trades"],
                                m["research_skew"], m["research_kurtosis"],
                                all_sharpes, grid_size)
        r["dsr"] = round(value, 6)
        if r["dsr"] >= DSR_THRESHOLD:
            dsr[r["spec_hash"]] = r["dsr"]
        else:
            r["stage"] = "rejected_dsr"

    # Pass 3: one-touch lockbox (stage 4) for every DSR survivor.
    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if survivors:
        store.touch_lockbox(ORDERFLOW_DOMAIN, 1)   # set-once for the domain
        for r in survivors:
            fb = fb_for(r["spec"])
            ctrl = control_for(r["spec"])
            tail = lockbox_dominant(r["spec"], ctrl, fb.full, fb.fence_index)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_of(tail) else "lockbox_fail"

    promoted = any(r["stage"] == "lockbox_pass" for r in rows)
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(ORDERFLOW_DOMAIN, 1, verdict)
    _write_verdict(out_root, verdict, rows, dsr)
    return verdict


def _write_verdict(out_root: Path, verdict: str, rows: list[dict],
                   dsr: dict[str, float]) -> None:
    lines = [
        "# orderflow_microstructure v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        f"- **Domain:** {ORDERFLOW_DOMAIN} (intraday order-flow microstructure"
        " on BTC/USDT:USDT 15m vs donchian_break control)",
        "- **Construction:** oi_flush_reversal / taker_flow_momentum /"
        " liquidity_sweep_reclaim + fixed_bracket{k_stop:2.0,m_tp:1.0,"
        "atr_period:14}.",
        "- **Promotion requires >=1 treatment spec to clear stages 1, 2, 3.5,"
        " DSR(>=0.95, n_trials=10), and 4 AND strictly dominate its"
        " donchian_break control on MAR & Sharpe at holdout, WF aggregate,"
        " and lockbox tail.",
        "",
        "| family | final stage | screen n | holdout trt MAR | WF folds |"
        " DSR | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["m"]
        fam = r["spec"].entry["family"]
        wf_folds = r["wf"]["folds"] if r.get("wf") else "-"
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        tail_mar = (f"{r['tail']['tail_treatment_mar']:.3f}"
                    if r.get("tail") else "-")
        lines.append(f"| {fam} | {r['stage']} | {m['screen_trades']} | "
                     f"{m['holdout_treatment_mar']:.3f} | {wf_folds} | "
                     f"{dsr_v} | {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2, no"
              " added family, no gate/exit relaxation. The intraday-horizon +"
              " reversal-exit lever is terminal for these families on a"
              " closed-negative verdict."]
    d = out_root / ORDERFLOW_DOMAIN
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.md").write_text("\n".join(lines))
