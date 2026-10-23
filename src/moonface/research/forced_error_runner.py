"""Dedicated runner for the forced_error lane (spec 2026-07-08)."""
from __future__ import annotations

from pathlib import Path

from moonface.core.metrics import deflated_sharpe
from moonface.kernel.divergence_null import surrogate_null
from moonface.research.forced_error import (
    FORCED_ERROR_DOMAIN, control_for, evaluate_dominant, forced_error_specs,
    lockbox_dominant, stage1_of, stage2_of, stage4_of)
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.kernel.lockbox import FencedBundle
from moonface.research.orderflow_wf import stage35_of, walk_forward
from moonface.kernel.spec import spec_from_json, spec_hash
from moonface.kernel.store import Store

FORCED_ERROR_START_MS = 1_598_918_400_000  # OI history begins 2020-09-01
LOCKBOX_FRACTION = 0.2


def register(store: Store, now_ms: int) -> None:
    fence_ts = now_ms - int((now_ms - FORCED_ERROR_START_MS) * LOCKBOX_FRACTION)
    if store.domain(FORCED_ERROR_DOMAIN, 1) is None:
        store.register_domain(FORCED_ERROR_DOMAIN, 1, "active",
                              {"runner": "forced_error"},
                              FORCED_ERROR_START_MS, now_ms, fence_ts)
        store.insert_grid(FORCED_ERROR_DOMAIN, 1, forced_error_specs())


def run_domain(store: Store, loader, out_root: Path) -> str:
    d = store.domain(FORCED_ERROR_DOMAIN, 1)
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(FORCED_ERROR_DOMAIN, 1)]
    grid_size = len(specs)
    # This lane has HETEROGENEOUS spec assets: Setup 1 needs OI only, Setup 2
    # needs OI + funding. Load ONE bundle from the union of every spec's asset
    # (all specs share exchange/symbol/timeframe; Setup 2 merely adds
    # funding_symbol) so both setups see the fields their generators require.
    load_asset: dict = {}
    for s in specs:
        load_asset.update(s.asset)
    fb = FencedBundle(loader(load_asset, d["start_ms"], d["end_ms"]),
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
        store.touch_lockbox(FORCED_ERROR_DOMAIN, 1)
        for r in survivors:
            ctrl = control_for(r["spec"])
            tail = lockbox_dominant(r["spec"], ctrl, fb.full, fb.fence_index)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_of(tail) else "lockbox_fail"

    promoted = any(r["stage"] == "lockbox_pass" for r in rows)
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(FORCED_ERROR_DOMAIN, 1, verdict)
    _write_verdict(out_root, verdict, rows)
    return verdict


def _write_verdict(out_root: Path, verdict: str, rows: list[dict]) -> None:
    lines = [
        "# forced_error v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        "- **Lane:** Forced-Error Harvesting — Setup 1 (Failed Breakout"
        " Harvest, SHORT) + Setup 2 (Failed Fade Squeeze, LONG),"
        " BTC/USDT:USDT 1h, each vs its isolation control.",
        "- **Promotion requires** stages 1,2,3.5, DSR(>=0.95, n_trials=8"
        " pooled), the cross-coupling surrogate-null gate, AND stage 4 with"
        " dominance over the paired control at holdout, WF, and lockbox tail.",
        "",
        "| family | (L,k) | final stage | screen n | holdout trt MAR | DSR |"
        " null p | tail trt MAR |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        p = r["spec"].entry["params"]
        m = r["m"]
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        null_p = f"{r['null']['p_value']:.3f}" if r.get("null") else "-"
        tail_mar = (f"{r['tail']['tail_treatment_mar']:.3f}"
                    if r.get("tail") else "-")
        lines.append(
            f"| {r['spec'].entry['family']} | ({p['lookback']},{p['k']}) |"
            f" {r['stage']} | {m['screen_trades']} |"
            f" {m['holdout_treatment_mar']:.3f} | {dsr_v} | {null_p} |"
            f" {tail_mar} |")
    lines += ["",
              "Kill rule (fired if negative): no v2, no grid expansion, no"
              " direction flip, no added family, no multi-asset, no signed-CVD"
              " swap without a NEW pre-registration."]
    out = out_root / FORCED_ERROR_DOMAIN
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.md").write_text("\n".join(lines))
