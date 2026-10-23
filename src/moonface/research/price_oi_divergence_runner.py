"""Dedicated runner for the price_oi_divergence lane."""
from __future__ import annotations

from pathlib import Path

from moonface.core.metrics import deflated_sharpe
from moonface.kernel.divergence_null import surrogate_null
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.kernel.lockbox import FencedBundle
from moonface.research.orderflow_wf import stage35_of, walk_forward
from moonface.research.price_oi_divergence import (
    DIVERGENCE_DOMAIN, control_for, divergence_specs, evaluate_dominant,
    lockbox_dominant, stage1_of, stage2_of, stage4_of)
from moonface.kernel.spec import spec_from_json, spec_hash
from moonface.kernel.store import Store

DIVERGENCE_START_MS = 1_598_918_400_000
LOCKBOX_FRACTION = 0.2


def register(store: Store, now_ms: int) -> None:
    fence_ts = now_ms - int((now_ms - DIVERGENCE_START_MS) * LOCKBOX_FRACTION)
    if store.domain(DIVERGENCE_DOMAIN, 1) is None:
        store.register_domain(DIVERGENCE_DOMAIN, 1, "active",
                              {"runner": "price_oi_divergence"},
                              DIVERGENCE_START_MS, now_ms, fence_ts)
        store.insert_grid(DIVERGENCE_DOMAIN, 1, divergence_specs())


def run_domain(store: Store, loader, out_root: Path) -> str:
    d = store.domain(DIVERGENCE_DOMAIN, 1)
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(DIVERGENCE_DOMAIN, 1)]
    grid_size = len(specs)
    fb = FencedBundle(loader(specs[0].asset, d["start_ms"], d["end_ms"]),
                      d["fence_ts"])
    research = fb.research()

    rows: list[dict] = []
    for spec in specs:
        row = {"spec_hash": spec_hash(spec), "spec": spec, "m": None,
               "wf": None, "null": None, "stage": "research"}
        ctrl = control_for(spec)
        m = evaluate_dominant(spec, ctrl, research, SCREEN_FRACTION)
        row["m"] = m
        rows.append(row)
        if not stage1_of(m):
            row["stage"] = "rejected_stage1"
            continue
        if not stage2_of(m):
            row["stage"] = "rejected_stage2"
            continue
        wf = walk_forward(spec, research, ctrl)
        row["wf"] = wf
        if not stage35_of(wf):
            row["stage"] = "rejected_wf"
            continue
        row["stage"] = "wf_pass"

    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    for r in rows:
        if r["stage"] != "wf_pass":
            continue
        m = r["m"]
        value = deflated_sharpe(m["research_sharpe"], m["research_trades"],
                                m["research_skew"], m["research_kurtosis"],
                                all_sharpes, grid_size)
        r["dsr"] = round(value, 6)
        if r["dsr"] < DSR_THRESHOLD:
            r["stage"] = "rejected_dsr"

    for r in rows:
        if r["stage"] != "wf_pass":
            continue
        null = surrogate_null(r["spec"], research)
        r["null"] = null
        if not null["passed"]:
            r["stage"] = "rejected_null"

    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if survivors:
        store.touch_lockbox(DIVERGENCE_DOMAIN, 1)
        for r in survivors:
            ctrl = control_for(r["spec"])
            tail = lockbox_dominant(r["spec"], ctrl, fb.full, fb.fence_index)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_of(tail) else "lockbox_fail"

    promoted = any(r["stage"] == "lockbox_pass" for r in rows)
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(DIVERGENCE_DOMAIN, 1, verdict)
    _write_verdict(out_root, verdict, rows)
    return verdict


def _write_verdict(out_root: Path, verdict: str, rows: list[dict]) -> None:
    lines = [
        "# price_oi_divergence v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        "- **Lane:** price↔OI standardized z-gap divergence, SHORT-only,"
        " BTC/USDT:USDT 1h, vs price-extension-only control.",
        "- **Construction:** z_r>=+k AND z_o<=-k +"
        " fixed_bracket{k_stop:2.0,m_tp:1.0,atr_period:14}; L in {3,6},"
        " k in {1.5,2.0}, W=180.",
        "- **Promotion requires** stages 1,2,3.5, DSR(>=0.95,n_trials=4),"
        " the cross-coupling surrogate-null gate, AND stage 4 with dominance"
        " over the price-only control at holdout, WF aggregate, and lockbox"
        " tail.",
        "",
        "| cell (L,k) | final stage | screen n | holdout trt MAR | DSR |"
        " null p | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        p = r["spec"].entry["params"]
        m = r["m"]
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        null_p = f"{r['null']['p_value']:.3f}" if r.get("null") else "-"
        tail_mar = (f"{r['tail']['tail_treatment_mar']:.3f}"
                    if r.get("tail") else "-")
        lines.append(
            f"| ({p['lookback']},{p['k']}) | {r['stage']} | {m['screen_trades']}"
            f" | {m['holdout_treatment_mar']:.3f} | {dsr_v} | {null_p} |"
            f" {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2, no"
              " added family, no direction flip, no CVD bolt-on, no grid"
              " expansion without a new pre-registration."]
    out = out_root / DIVERGENCE_DOMAIN
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.md").write_text("\n".join(lines))
