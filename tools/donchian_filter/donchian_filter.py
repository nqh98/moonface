#!/usr/bin/env python3
"""Staged paper-research CLI: Donchian 40/20 + ADX trend-strength entry gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.donchian_filter import grid as G
from moonface.research.donchian_filter.adx import adx_series
from moonface.research.donchian_filter.data import load
from moonface.research.donchian_filter.evaluate import (
    base_trades,
    gate,
    overlapping_robust_frac,
    slice_metrics,
)
from moonface.research.donchian_filter.select import (
    qualifies,
    holdout_verdict,
    select_threshold,
)


def _write(out_dir, name, doc):
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(json.dumps(doc, indent=2, sort_keys=True, default=str))


def _slice_eval(candles, funding):
    base = base_trades(candles, funding)
    adx = adx_series(candles, G.ADX_PERIOD)
    n = len(candles)
    base_m = slice_metrics(base)
    base_rf = overlapping_robust_frac(base, n, G.YEAR_BARS, G.QUARTER_BARS)
    rows = []
    for thr in G.THRESHOLDS:
        g = gate(base, adx, thr)
        gm = slice_metrics(g)
        grf = overlapping_robust_frac(g, n, G.YEAR_BARS, G.QUARTER_BARS)
        ok, reasons = qualifies(base_m, gm, base_rf, grf)
        rows.append({
            "threshold": thr,
            "gated": gm,
            "robust_frac": grf,
            "qualifies": ok,
            "reasons": reasons,
        })
    return {"base": base_m, "base_robust_frac": base_rf, "rows": rows}


def _register(args):
    _write(args.out_dir, "PREREGISTRATION.json", {
        "lane": "donchian_adx_filter",
        "core_frozen": "replace(_BASE, entry_n=40, trail_n=20) exit=trail",
        "mechanism": "enter only if ADX(14) >= threshold (subset of base trades)",
        "adx_period": G.ADX_PERIOD,
        "thresholds": list(G.THRESHOLDS),
        "n_trials": G.N_TRIALS,
        "windows": {
            "train": [G.TRAIN_START, G.TRAIN_END],
            "validate": [G.TRAIN_END, G.VALIDATE_END],
            "sealed": [G.VALIDATE_END, G.SEALED_END],
        },
        "selection": (
            "train-only: qualify = net_r>=0.90*base AND maxDD strictly better "
            "AND robust_frac>=base AND trades>=0.50*base; pick least-negative train maxDD"
        ),
        "holdout_labels": ["IMPROVES", "NEUTRAL", "DESTROYS_INACTIVE"],
        "floors": {
            "trend_capture": G.TREND_CAPTURE_FRAC,
            "activity": G.ACTIVITY_FRAC,
            "holdout_min_trades": G.HOLDOUT_MIN_TRADES,
            "neutral_tol_r": G.NEUTRAL_TOL_R,
        },
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
    thr = select_threshold(lb["rows"])
    if thr is None:
        _write(args.out_dir, "frozen_candidate.json", {
            "frozen": None,
            "reason": "no train qualifier",
            "rows": lb["rows"],
        })
    else:
        row = next(r for r in lb["rows"] if r["threshold"] == thr)
        _write(args.out_dir, "frozen_candidate.json", {"frozen": thr, "train_row": row})
    return 0


def _validate(args):
    fc = json.loads((Path(args.out_dir) / "frozen_candidate.json").read_text())
    if not fc.get("frozen"):
        _write(args.out_dir, "RESULT.json", {
            "verdict": "negative",
            "reason": "no frozen candidate; holdout not opened",
        })
        return 0
    thr = fc["frozen"]
    candles, funding = load(G.VALIDATE_END, G.SEALED_END, args.cache_dir)
    base = base_trades(candles, funding)
    adx = adx_series(candles, G.ADX_PERIOD)
    base_m = slice_metrics(base)
    gated_m = slice_metrics(gate(base, adx, thr))
    verdict = holdout_verdict(base_m, gated_m)
    _write(args.out_dir, "RESULT.json", {
        "threshold": thr,
        "sealed_base": base_m,
        "sealed_gated": gated_m,
        "verdict": verdict,
    })
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="donchian-filter")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--register", action="store_true")
    g.add_argument("--explore", action="store_true")
    g.add_argument("--select", action="store_true")
    g.add_argument("--validate", action="store_true")
    p.add_argument("--cache-dir", default="cache/swing")
    p.add_argument("--out-dir", default="experiments/donchian_filter")
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
