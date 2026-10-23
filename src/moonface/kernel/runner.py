# src/moonface/research/runner.py
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import moonface.research.ladder as ladder
from moonface.core.bundle import DataBundle
from moonface.core.provenance import code_hash
from moonface.core.stats import series_fingerprint
from moonface.kernel import dsr as kernel_dsr
from moonface.kernel.lockbox import FencedBundle
from moonface.kernel.report import write_domain_report
from moonface.kernel.spec import spec_from_json, spec_hash
from moonface.kernel.store import Store

_STAGE1_CODE_MODULES = [
    "src/moonface/kernel/dsr.py",
    "src/moonface/kernel/runner.py",
    "src/moonface/core/metrics.py",
    "src/moonface/research/ladder.py",
]

Loader = Callable[[dict, int, int], DataBundle]  # (asset, start_ms, end_ms)

ERROR_RATE_LIMIT = 0.2


@dataclass(frozen=True)
class Boundary:
    kind: str  # idle | budget | awaiting_gate | blocked | errors | closed
    domain: str | None
    message: str


def run(store: Store, loader: Loader, out_root: Path,
        budget: int | None = None, only_domain: str | None = None) -> Boundary:
    """Drain pre-registered grids until a domain boundary or the budget.
    Resumable and idempotent: every stage transition is persisted before the
    next row is touched."""
    spent = 0
    for d in store.domains_in_order():
        name, version = d["name"], d["version"]
        if only_domain is not None and name != only_domain:
            continue
        if d["config"].get("runner") not in (None, "generic"):
            continue  # bespoke-runner domains (e.g. funding_fade_voltarget) have their own driver
        if d["status"] in ("closed_positive", "closed_negative", "awaiting_gate",
                           "shelved"):
            continue
        if d["status"] == "blocked":
            return Boundary("blocked", name,
                            f"{name} v{version} is blocked: its signal generator"
                            " is not implemented yet")

        bundles: dict[str, FencedBundle] = {}

        def fenced(asset: dict) -> FencedBundle:
            key = json.dumps(asset, sort_keys=True)
            if key not in bundles:
                bundles[key] = FencedBundle(
                    loader(asset, d["start_ms"], d["end_ms"]), d["fence_ts"])
            return bundles[key]

        if d["status"] == "lockbox_open":
            return _run_lockbox(store, d, fenced, out_root)

        # stages 1+2: loop until no row makes progress (errors retry up to the
        # store's attempt cap, then leave the pool as status='error')
        while True:
            progressed = False
            for from_status in ("pending", "screened"):
                for row in store.rows(name, version, status=from_status):
                    if budget is not None and spent >= budget:
                        return Boundary("budget", name,
                                        f"stage budget of {budget} reached")
                    spent += 1
                    progressed = True
                    try:
                        if from_status == "pending":
                            _stage1(store, row, fenced)
                        else:
                            _stage2(store, row)
                    except Exception as exc:  # noqa: BLE001 - per-row isolation
                        store.record_error(row["spec_hash"], repr(exc))
            if not progressed:
                break

        counts = store.counts(name, version)
        if counts.get("error", 0) > ERROR_RATE_LIMIT * max(d["grid_size"], 1):
            store.set_domain_status(name, version, "awaiting_gate")
            write_domain_report(store, name, version, out_root)
            return Boundary("errors", name,
                            f"{counts.get('error', 0)} of {d['grid_size']} rows"
                            " errored out; review the report")

        if not d["stage3_done"]:
            dsr = kernel_dsr.stage3_dsr(store.rows(name, version),
                                        store.lineage_trial_count(name))
            for row in store.rows(name, version, status="oos_pass"):
                value = dsr[row["spec_hash"]]
                new = ("corrected_survivor" if value >= kernel_dsr.DSR_THRESHOLD
                       else "rejected")
                store.advance(row["spec_hash"], new, {"dsr": value})
            store.mark_stage3_done(name, version)

        counts = store.counts(name, version)
        survivors = counts.get("corrected_survivor", 0)
        if survivors == 0:
            store.set_domain_status(name, version, "closed_negative")
            write_domain_report(store, name, version, out_root)
            return Boundary("closed", name,
                            f"{name} closed negative: no corrected survivor")
        store.set_domain_status(name, version, "awaiting_gate")
        write_domain_report(store, name, version, out_root)
        return Boundary(
            "awaiting_gate", name,
            f"{survivors} corrected survivor(s); review the report, then run"
            f" `python tools/research.py gate {name} --open-lockbox`")
    return Boundary("idle", None, "no active domain has work")


def _stage1(store: Store, row: dict, fenced) -> None:
    spec = spec_from_json(row["spec_json"])
    research = fenced(spec.asset).research()
    m = ladder.evaluate_research(spec, research)
    m["registration_hash"] = spec_hash(spec)
    m["data_fingerprint"] = series_fingerprint(research.candles)
    m["code_hash"] = code_hash(_STAGE1_CODE_MODULES)
    if m["max_abs_r"] > ladder.R_SANITY_CAP:
        store.advance(row["spec_hash"], "anomaly", m)
        return
    ok = ladder.stage1_passed(m)
    store.advance(row["spec_hash"], "screened" if ok else "rejected", m)


def _stage2(store: Store, row: dict) -> None:
    ok = ladder.stage2_passed(row["stage_results"])
    store.advance(row["spec_hash"], "oos_pass" if ok else "rejected", {})


def _run_lockbox(store: Store, d: dict, fenced, out_root: Path) -> Boundary:
    name, version = d["name"], d["version"]
    store.touch_lockbox(name, version)  # set-once; raises on a second spend
    any_pass = False
    for row in store.rows(name, version, status="corrected_survivor"):
        spec = spec_from_json(row["spec_json"])
        fb = fenced(spec.asset)
        stream = ladder.r_stream(spec, fb.full)
        m = kernel_dsr.evaluate_lockbox(stream, spec, fb.fence_index)
        passed = ladder.stage4_passed(m)
        store.advance(row["spec_hash"],
                      "lockbox_pass" if passed else "lockbox_fail", m)
        any_pass = any_pass or passed
    final = "closed_positive" if any_pass else "closed_negative"
    store.set_domain_status(name, version, final)
    write_domain_report(store, name, version, out_root)
    return Boundary("closed", name, f"{name} {final} after the lockbox")
