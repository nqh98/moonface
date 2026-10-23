"""Staged paper-research CLI: macro-regime STRATEGY-SELECTOR (non-Donchian).

risk-on -> atr_channel_break (trend); risk-off -> reversion_in_range (MR) or flat.
Decided by the practical bar + beats-both-controls + sealed confirmation + a
swap falsification control. Paper-only: never touches promotion/journal/EXIT.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from moonface.research.regime_overlay.regime import REGIME_DEFS
from moonface.research.regime_selector import grid as G
from moonface.research.regime_selector.data import load_btc, load_macro
from moonface.research.regime_selector.evaluate import (beats_controls,
                                                        cell_vector,
                                                        control_vector,
                                                        practical_pass)

_REG = {r.id: r for r in REGIME_DEFS}


def _write(out_dir, name, doc):
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(json.dumps(doc, indent=2, sort_keys=True))


def _controls(candles, macro, first_ts, last_ts):
    # always_* ignore regime; compute once with an arbitrary regime def.
    any_reg = _REG[G.REGIME_IDS[0]]
    trend = control_vector(candles, macro, any_reg, "always_trend", first_ts, last_ts)
    mr = control_vector(candles, macro, any_reg, "always_mr", first_ts, last_ts)
    return trend, mr


def _eval(candles, macro, first_ts, last_ts):
    trend_c, mr_c = _controls(candles, macro, first_ts, last_ts)
    swap = {rid: control_vector(candles, macro, _REG[rid], "swap", first_ts, last_ts)
            for rid in G.REGIME_IDS}
    rows = []
    for c in G.CELLS:
        v = cell_vector(candles, macro, _REG[c.regime_id], c.riskoff_action,
                        first_ts, last_ts)
        rows.append({"cell_id": c.cell_id, "regime_id": c.regime_id,
                     "riskoff_action": c.riskoff_action, "vector": v,
                     "practical": practical_pass(v),
                     "vs_controls": beats_controls(v, trend_c, mr_c)})
    swap_pass = {rid: (practical_pass(swap[rid])["all_pass"]
                       and beats_controls(swap[rid], trend_c, mr_c)["beats_both"])
                 for rid in G.REGIME_IDS}
    return {"trend": trend_c, "mr": mr_c, "swap": swap,
            "swap_pass": swap_pass, "cells": rows}


def _register(args):
    doc = {
        "lane": "macro_regime_strategy_selector",
        "grid": [c.cell_id for c in G.CELLS],
        "trend_base": {"family": G.TREND_FAMILY, "params": G.TREND_PARAMS,
                       "exit": G.TREND_EXIT, "exit_params": G.TREND_EXIT_PARAMS,
                       "h": G.TREND_H},
        "mr_base": {"family": G.MR_FAMILY, "params": G.MR_PARAMS,
                    "exit": G.MR_EXIT, "exit_params": G.MR_EXIT_PARAMS,
                    "h": G.MR_H},
        "regimes": list(G.REGIME_IDS), "riskoff_actions": list(G.RISKOFF_ACTIONS),
        "controls": list(G.CONTROL_KINDS),
        "windows": {"train": [G.TRAIN_START, G.TRAIN_END],
                    "validate": [G.VALIDATE_START, G.VALIDATE_END],
                    "sealed": [G.SEALED_START, G.SEALED_END]},
        "n_trials": G.N_TRIALS,
        "gate": ("practical_pass(validate) AND beats_both_controls(validate) AND "
                 "sealed practical_pass+beats_net AND swap-control fails"),
    }
    _write(args.out_dir, "PREREGISTRATION.json", doc)
    return 0


def _explore(args):
    candles = load_btc(G.TRAIN_START, G.TRAIN_END, args.cache_dir)
    macro = load_macro(args.cache_dir)
    res = _eval(candles, macro, G.TRAIN_START, G.TRAIN_END)
    res["cells"].sort(key=lambda r: r["vector"]["net_r"], reverse=True)
    _write(args.out_dir, "explore_leaderboard.json", res)
    return 0


def _advancing(res):
    return [r for r in res["cells"]
            if r["practical"]["all_pass"]
            and r["vs_controls"]["beats_both"]
            and not res["swap_pass"][r["regime_id"]]]


def _select(args):
    candles = load_btc(G.VALIDATE_START, G.VALIDATE_END, args.cache_dir)
    macro = load_macro(args.cache_dir)
    res = _eval(candles, macro, G.VALIDATE_START, G.VALIDATE_END)
    survivors = _advancing(res)
    if not survivors:
        _write(args.out_dir, "frozen_candidate.json",
               {"frozen": None, "reason": "no validate survivor", "validate": res})
        return 0
    survivors.sort(key=lambda r: (r["vector"]["net_r"],
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
    candles = load_btc(G.SEALED_START, G.SEALED_END, args.cache_dir)
    macro = load_macro(args.cache_dir)
    cv = cell_vector(candles, macro, _REG[cell.regime_id], cell.riskoff_action,
                     G.SEALED_START, G.SEALED_END)
    trend_c, mr_c = _controls(candles, macro, G.SEALED_START, G.SEALED_END)
    pp = practical_pass(cv)
    vb = beats_controls(cv, trend_c, mr_c, recent=False)
    verdict = ("paper_accept" if pp["all_pass"] and vb["beats_both"] else "negative")
    _write(args.out_dir, "RESULT.json",
           {"cell": cell.cell_id, "sealed_cell_vector": cv,
            "sealed_trend_control": trend_c, "sealed_mr_control": mr_c,
            "practical_pass": pp, "beats_controls": vb, "verdict": verdict})
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="regime-selector-btc")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--register", action="store_true")
    g.add_argument("--explore", action="store_true")
    g.add_argument("--select", action="store_true")
    g.add_argument("--validate", action="store_true")
    p.add_argument("--cache-dir", default="cache/swing")
    p.add_argument("--out-dir", default="experiments/regime_selector")
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
