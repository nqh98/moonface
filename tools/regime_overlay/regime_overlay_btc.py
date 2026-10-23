"""Staged paper-research CLI: Donchian x macro-regime overlay.

DSR is reported elsewhere/not gated; this lane decides by the practical bar.
Paper-only: never touches promotion/journal/EXIT_REGISTRY.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from moonface.research.regime_overlay import grid as G
from moonface.research.regime_overlay.data import load_btc, load_macro
from moonface.research.regime_overlay.evaluate import (base_vector, beats_base,
                                                       cell_vector,
                                                       practical_pass)
from moonface.research.regime_overlay.overlay import MODES
from moonface.research.regime_overlay.regime import REGIME_DEFS
from tools.engine.swing_donchian import _BASE

_REG = {r.id: r for r in REGIME_DEFS}


def base_params():
    return replace(_BASE, entry_n=40, trail_n=20)


def _write(out_dir, name, doc):
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(json.dumps(doc, indent=2, sort_keys=True))


def _eval_cells(candles, funding, macro, first_ts, last_ts):
    bp = base_params()
    base = base_vector(candles, funding, bp, first_ts, last_ts)
    rows = []
    for c in G.CELLS:
        v = cell_vector(candles, funding, bp, _REG[c.regime_id], macro,
                        c.mode, first_ts, last_ts)
        rows.append({"cell_id": c.cell_id, "regime_id": c.regime_id,
                     "mode": c.mode, "vector": v,
                     "practical": practical_pass(v),
                     "vs_base": beats_base(v, base)})
    return base, rows


def _register(args):
    bp = base_params()
    doc = {
        "lane": "donchian_macro_regime_overlay",
        "grid": [c.cell_id for c in G.CELLS],
        "regimes": [{"id": r.id, "name": r.name} for r in REGIME_DEFS],
        "modes": list(MODES),
        "windows": {"train": [G.TRAIN_START, G.TRAIN_END],
                    "validate": [G.VALIDATE_START, G.VALIDATE_END],
                    "sealed": [G.SEALED_START, G.SEALED_END]},
        "base_params": asdict(bp),
        "n_trials": G.N_TRIALS,
        "gate": "practical (DSR reported, not gated)",
    }
    _write(args.out_dir, "PREREGISTRATION.json", doc)
    return 0


def _explore(args):
    candles, funding = load_btc(G.TRAIN_START, G.TRAIN_END, args.cache_dir)
    macro = load_macro(args.cache_dir)
    base, rows = _eval_cells(candles, funding, macro, G.TRAIN_START, G.TRAIN_END)
    rows.sort(key=lambda r: r["vs_base"]["delta_trailing_365d"], reverse=True)
    _write(args.out_dir, "explore_leaderboard.json",
           {"base": base, "cells": rows})
    return 0


def _advancing(rows):
    return [r for r in rows
            if r["practical"]["all_pass"] and r["vs_base"]["beats_recent"]]


def _select(args):
    candles, funding = load_btc(G.VALIDATE_START, G.VALIDATE_END, args.cache_dir)
    macro = load_macro(args.cache_dir)
    lead = json.loads((Path(args.out_dir) / "explore_leaderboard.json").read_text())
    train_adv = {r["cell_id"] for r in _advancing(lead["cells"])}
    base, rows = _eval_cells(candles, funding, macro,
                             G.VALIDATE_START, G.VALIDATE_END)
    survivors = [r for r in _advancing(rows) if r["cell_id"] in train_adv]
    if not survivors:
        _write(args.out_dir, "frozen_candidate.json",
               {"frozen": None, "reason": "no train+validate survivor"})
        return 0
    survivors.sort(key=lambda r: (r["vs_base"]["delta_trailing_365d"],
                                  r["vector"]["net_r"],
                                  r["vector"]["max_drawdown_r"]), reverse=True)
    _write(args.out_dir, "frozen_candidate.json",
           {"frozen": survivors[0]["cell_id"], "validate_row": survivors[0]})
    return 0


def _validate(args):
    fc = json.loads((Path(args.out_dir) / "frozen_candidate.json").read_text())
    if not fc.get("frozen"):
        _write(args.out_dir, "RESULT.json",
               {"verdict": "negative", "reason": "no frozen candidate"})
        return 0
    cell = next(c for c in G.CELLS if c.cell_id == fc["frozen"])
    candles, funding = load_btc(G.SEALED_START, G.SEALED_END, args.cache_dir)
    macro = load_macro(args.cache_dir)
    bp = base_params()
    cv = cell_vector(candles, funding, bp, _REG[cell.regime_id], macro,
                     cell.mode, G.SEALED_START, G.SEALED_END)
    bv = base_vector(candles, funding, bp, G.SEALED_START, G.SEALED_END)
    pp = practical_pass(cv)
    vb = beats_base(cv, bv)
    verdict = ("forward_paper_watch"
               if pp["all_pass"] and vb["beats_recent"] else "negative")
    _write(args.out_dir, "RESULT.json",
           {"cell": cell.cell_id, "sealed_cell_vector": cv,
            "sealed_base_vector": bv, "practical_pass": pp,
            "beats_base": vb, "verdict": verdict})
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="regime-overlay-btc")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--register", action="store_true")
    g.add_argument("--explore", action="store_true")
    g.add_argument("--select", action="store_true")
    g.add_argument("--validate", action="store_true")
    p.add_argument("--start-ms", type=int, default=None)
    p.add_argument("--end-ms", type=int, default=None)
    p.add_argument("--cache-dir", default="cache/swing")
    p.add_argument("--out-dir", default="experiments/regime_overlay")
    return p


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.register:
        return _register(args)
    if args.explore:
        return _explore(args)
    if args.select:
        return _select(args)
    return _validate(args)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
