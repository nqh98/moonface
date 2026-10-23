# src/moonface/research/voltarget_runner.py
"""Dedicated runner for the funding_fade_voltarget domain (spec 2026-07-02).

Reuses Store (registration + one-touch lockbox) and FencedBundle (one-touch
tail), but drives the paired vol-targeted ladder + walk-forward itself — the
generic runner.run cannot express per-trade vol-targeted sizing. The generic
runner skips any domain whose config.runner is neither None nor 'generic'
(see the guard added to runner.run)."""
from __future__ import annotations

import json
from pathlib import Path

from moonface.core.metrics import deflated_sharpe
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.kernel.lockbox import FencedBundle
from moonface.kernel.spec import HypothesisSpec, spec_from_json, spec_hash
from moonface.kernel.store import Store
from moonface.research.voltarget import (CONTROL_FRACTION, VOLTARGET_ENTRY,
                                         VOLTARGET_EXIT, paired_lockbox,
                                         paired_research, stage1_paired,
                                         stage2_paired, stage4_paired)
from moonface.research.voltarget_wf import stage35_paired, walk_forward_paired

VOLTARGET_DOMAIN = "funding_fade_voltarget"
VOLTARGET_START_MS = 1_577_836_800_000   # 2020-01-01 UTC
LOCKBOX_FRACTION = 0.2
VOLTARGET_ASSETS = [
    {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "4h",
     "funding_symbol": "ETH/USDT:USDT"},
    {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "4h",
     "funding_symbol": "SOL/USDT:USDT"},
]


def voltarget_specs() -> list[HypothesisSpec]:
    fam, ep = VOLTARGET_ENTRY
    name, xp = VOLTARGET_EXIT
    return [HypothesisSpec(domain=VOLTARGET_DOMAIN, version=1, asset=a,
                           entry={"family": fam, "params": ep},
                           exit={"name": name, "params": xp},
                           fraction=CONTROL_FRACTION)
            for a in VOLTARGET_ASSETS]


def register(store: Store, now_ms: int) -> None:
    """Freeze the window + fence and insert the 2-spec grid. Idempotent."""
    fence_ts = now_ms - int((now_ms - VOLTARGET_START_MS) * LOCKBOX_FRACTION)
    if store.domain(VOLTARGET_DOMAIN, 1) is None:
        store.register_domain(VOLTARGET_DOMAIN, 1, "active",
                              {"runner": "voltarget", "assets": VOLTARGET_ASSETS},
                              VOLTARGET_START_MS, now_ms, fence_ts)
        store.insert_grid(VOLTARGET_DOMAIN, 1, voltarget_specs())


def _dsr(passing: list[dict], all_sharpes: list[float], grid_size: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in passing:
        m = r["m"]
        out[r["spec_hash"]] = deflated_sharpe(
            m["research_sharpe"], m["research_trades"], m["research_skew"],
            m["research_kurtosis"], all_sharpes, grid_size)
    return out


def run_domain(store: Store, loader, out_root: Path) -> str:
    d = store.domain(VOLTARGET_DOMAIN, 1)
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(VOLTARGET_DOMAIN, 1)]
    grid_size = len(specs)
    fenced: dict[str, FencedBundle] = {}

    def fb_for(spec):
        key = json.dumps(spec.asset, sort_keys=True)
        if key not in fenced:
            fenced[key] = FencedBundle(loader(spec.asset, d["start_ms"], d["end_ms"]),
                                       d["fence_ts"])
        return fenced[key]

    # Pass 1: stages 1, 2, 3.5 per spec; collect research metrics for ALL specs
    # (DSR trial variance uses every spec's research Sharpe, per ladder.stage3_dsr).
    rows: list[dict] = []
    for spec in specs:
        h = spec_hash(spec)
        fb = fb_for(spec)
        research = fb.research()
        m = paired_research(spec, research, SCREEN_FRACTION)
        rows.append({"spec_hash": h, "spec": spec, "m": m, "wf": None,
                     "stage": "research"})
        if not stage1_paired(m):
            rows[-1]["stage"] = "rejected_stage1"
            continue
        if not stage2_paired(m):
            rows[-1]["stage"] = "rejected_stage2"
            continue
        wf = walk_forward_paired(spec, research)
        rows[-1]["wf"] = wf
        if not stage35_paired(wf):
            rows[-1]["stage"] = "rejected_wf"
            continue
        rows[-1]["stage"] = "wf_pass"

    # Pass 2: DSR (stage 3) across all specs that passed 1/2/3.5.
    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    wf_passers = [r for r in rows if r["stage"] == "wf_pass"]
    dsr = _dsr(wf_passers, all_sharpes, grid_size) if wf_passers else {}
    for r in wf_passers:
        r["dsr"] = dsr.get(r["spec_hash"], 0.0)
        if r["dsr"] < DSR_THRESHOLD:
            r["stage"] = "rejected_dsr"

    # Pass 3: one-touch lockbox (stage 4) only if EVERY spec survived 1..3.5+DSR.
    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if grid_size > 0 and len(survivors) == grid_size:
        store.touch_lockbox(VOLTARGET_DOMAIN, 1)
        for r in survivors:
            fb = fb_for(r["spec"])
            tail = paired_lockbox(r["spec"], fb.full, fb.fence_index, SCREEN_FRACTION)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_paired(tail) else "lockbox_fail"

    promoted = (grid_size > 0
                and all(r["stage"] == "lockbox_pass" for r in rows))
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(VOLTARGET_DOMAIN, 1, verdict)
    _write_verdict(out_root, verdict, rows, dsr)
    return verdict


def _write_verdict(out_root: Path, verdict: str, rows: list[dict],
                   dsr: dict[str, float]) -> None:
    lines = [
        "# funding_fade_voltarget v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        f"- **Domain:** {VOLTARGET_DOMAIN} (vol/risk-targeted sizing vs fixed-fractional)",
        f"- **Construction:** funding_fade {VOLTARGET_ENTRY[1]} + {VOLTARGET_EXIT[0]}"
        f" {VOLTARGET_EXIT[1]}",
        "- **Promotion requires BOTH assets to clear stages 1-4 and dominate the"
        " control on MAR & Sharpe at holdout, WF aggregate, and lockbox tail.",
        "",
        "| asset | final stage | screen n | holdout trt MAR | WF folds | DSR | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["m"]
        symbol = r["spec"].asset["symbol"]
        wf_folds = r["wf"]["folds"] if r.get("wf") else "-"
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        tail_mar = f"{r['tail']['tail_treatment_mar']:.3f}" if r.get("tail") else "-"
        lines.append(f"| {symbol} | {r['stage']} | {m['screen_trades']} | "
                     f"{m['holdout_treatment_mar']:.3f} | {wf_folds} | {dsr_v} | {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2, no fraction"
              " grid, no budget relaxation. The vol/risk-targeting lever is terminal"
              " for funding_fade + fixed_bracket on a closed-negative verdict."]
    d = out_root / VOLTARGET_DOMAIN
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.md").write_text("\n".join(lines))
