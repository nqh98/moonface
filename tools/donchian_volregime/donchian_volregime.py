#!/usr/bin/env python3
"""Staged paper-research CLI: BTC 4h Donchian 40/20 × volatility-regime permission gate.

Mechanism: keep a byte-frozen Donchian base trade only if its ENTRY bar is in the
cell's 'High-Vol + Expansion / Trending' regime; else WAIT. Paper-only: never
touches promotion/journal/EXIT_REGISTRY. See
docs/research-log/specs/2026-07-02-donchian-volregime-design.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.donchian_volregime import grid as G
from moonface.research.donchian_volregime.data import load
from moonface.research.donchian_volregime.evaluate import (
    base_trades,
    cell_flags,
    gate,
    overlapping_robust_frac,
    slice_metrics,
)
from moonface.research.donchian_volregime.llm_gate import SCHEMA_VERSION
from moonface.research.donchian_volregime.select import (
    qualifies,
    sealed_verdict,
    select_cell,
)


def _write(out_dir, name, doc):
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(json.dumps(doc, indent=2, sort_keys=True, default=str))


def _slice_eval(candles, funding):
    base = base_trades(candles, funding)
    n = len(candles)
    base_m = slice_metrics(base)
    base_rf = overlapping_robust_frac(base, n, G.YEAR_BARS, G.QUARTER_BARS)
    rows = []
    for cell in G.CELLS:
        flags = cell_flags(candles, cell)
        g = gate(base, flags)
        gm = slice_metrics(g)
        grf = overlapping_robust_frac(g, n, G.YEAR_BARS, G.QUARTER_BARS)
        ok, reasons = qualifies(base_m, gm, base_rf, grf)
        rows.append({
            "cell": cell,
            "gated": gm,
            "robust_frac": grf,
            "qualifies": ok,
            "reasons": reasons,
        })
    return {"base": base_m, "base_robust_frac": base_rf, "rows": rows}


def _register(args):
    _write(args.out_dir, "PREREGISTRATION.json", {
        "lane": "donchian_volregime",
        "core_frozen": "replace(_BASE, entry_n=40, trail_n=20) exit=trail long_only",
        "mechanism": (
            "enter only if entry-bar regime allowed (subset of base trades); "
            "else WAIT"
        ),
        "cells": list(G.CELLS),
        "n_trials": G.N_TRIALS,
        "features_cfg": G.CFG,
        "windows": {
            "train": [G.TRAIN_START, G.TRAIN_END],
            "validate": [G.TRAIN_END, G.VALIDATE_END],
            "sealed": [G.VALIDATE_END, G.SEALED_END],
        },
        "selection": (
            "train-only qualify = net_r>=0.90*base AND maxDD strictly better AND "
            "robust_frac>=base AND trades>=0.50*base; pick least-negative train maxDD"
        ),
        "sealed_verdict": (
            "PAPER_CANDIDATE iff gated net_r>0 AND PF>=1.0 AND maxDD better than base "
            "AND net_r>base; else NEGATIVE; INACTIVE if n<10"
        ),
        "controls": ["donchian_filter (ADX, closed negative)",
                     "regime_overlay (macro, closed negative)"],
        "kill_rule": "closed-negative -> no re-tune/new-features/flip/exit-change; terminal",
    })
    return 0


def _register_llm(args):
    _write(args.out_dir, "LLM_FORWARD_REGISTRATION.json", {
        "lane": "donchian_volregime_llm_veto",
        "role": "forward-only permission/veto layer; NEVER decides LONG/SHORT/exit/stop/target",
        "schema_version": SCHEMA_VERSION,
        "labels": ["allow", "veto", "reduce_risk", "uncertain"],
        "decision_rule": (
            "veto|uncertain->WAIT; donchian WAIT or !quant_allow->WAIT; "
            "reduce_risk+LONG+quant->LONG@0.5; allow+LONG+quant->LONG@1.0"
        ),
        "hindsight_note": "no historical backtest; validated forward on paper only",
        "t0_ms": args.t0,
        "enabled": False,
    })
    return 0


def _explore(args):
    tr_c, tr_f = load(G.TRAIN_START, G.TRAIN_END, args.cache_dir)
    va_c, va_f = load(G.TRAIN_END, G.VALIDATE_END, args.cache_dir)
    train = _slice_eval(tr_c, tr_f)
    val = _slice_eval(va_c, va_f)
    _write(args.out_dir, "explore_leaderboard.json", {
        "base_train": train["base"],
        "base_train_robust_frac": train["base_robust_frac"],
        "rows": train["rows"],
        "validate_report": {"base": val["base"], "rows": val["rows"]},
    })
    return 0


def _select(args):
    lb = json.loads((Path(args.out_dir) / "explore_leaderboard.json").read_text())
    cell = select_cell(lb["rows"])
    if cell is None:
        _write(args.out_dir, "frozen_candidate.json", {
            "frozen": None,
            "reason": "no train qualifier",
            "rows": lb["rows"],
        })
    else:
        row = next(r for r in lb["rows"] if r["cell"] == cell)
        _write(args.out_dir, "frozen_candidate.json", {"frozen": cell, "train_row": row})
    return 0


def _validate(args):
    fc = json.loads((Path(args.out_dir) / "frozen_candidate.json").read_text())
    if not fc.get("frozen"):
        _write(args.out_dir, "RESULT.json", {
            "verdict": "negative",
            "reason": "no frozen candidate; holdout not opened",
        })
        return 0
    cell = fc["frozen"]
    candles, funding = load(G.VALIDATE_END, G.SEALED_END, args.cache_dir)
    base = base_trades(candles, funding)
    base_m = slice_metrics(base)
    gated_m = slice_metrics(gate(base, cell_flags(candles, cell)))
    verdict = sealed_verdict(base_m, gated_m)
    _write(args.out_dir, "RESULT.json", {
        "cell": cell,
        "sealed_base": base_m,
        "sealed_gated": gated_m,
        "verdict": verdict,
    })
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="donchian-volregime")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--register", action="store_true")
    g.add_argument("--register-llm", action="store_true")
    g.add_argument("--explore", action="store_true")
    g.add_argument("--select", action="store_true")
    g.add_argument("--validate", action="store_true")
    p.add_argument("--cache-dir", default="cache/swing")
    p.add_argument("--out-dir", default="experiments/donchian_volregime")
    p.add_argument("--t0", type=int, default=0, help="forward t0 (ms) for --register-llm")
    return p


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.register:
        return _register(args)
    if args.register_llm:
        return _register_llm(args)
    if args.explore:
        return _explore(args)
    if args.select:
        return _select(args)
    return _validate(args)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
