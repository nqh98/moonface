#!/usr/bin/env python3
"""Staged BTC long/short tournament CLI.

Paper-only. The lane is frozen up front, explores on the train slice, freezes
train survivors, and then opens validate/sealed once at the final stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.exogenous.fred_data import fetch_fred_series  # noqa: E402
from moonface.research.ls_tournament.grid import (  # noqa: E402
    TIMEFRAMES,
    all_configs,
    config_doc,
)
from moonface.research.ls_tournament.evaluate import run_explore  # noqa: E402
from moonface.research.ls_tournament.pipeline import freeze_candidates, render_findings  # noqa: E402
from moonface.research.ls_tournament.select import select  # noqa: E402
from moonface.research.ls_tournament.validate import validate_all  # noqa: E402
from moonface.data.series import fetch_metrics_history  # noqa: E402
from moonface.research.regime_selector.data import load_macro  # noqa: E402
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles  # noqa: E402

MIN_BARS = 300
SYMBOL = "BTCUSDT"


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_60_20_20(candles):
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    return candles[:a], candles[a:b], candles[b:]


def _load_timeframes(symbol, start_ms, end_ms, cache_dir) -> dict:
    return {tf: fetch_perp_candles(symbol, tf, start_ms, end_ms, cache_dir)
            for tf in TIMEFRAMES}


def _load_context(start_ms: int, end_ms: int, cache_dir: str) -> dict:
    funding = fetch_funding_rates(SYMBOL, start_ms, end_ms, cache_dir)
    macro = load_macro(cache_dir, fetch=fetch_fred_series)
    raw = fetch_metrics_history(SYMBOL, start_ms, end_ms, cache_dir)
    oi_points = [(ts, f["sum_open_interest"]) for ts, f in raw if "sum_open_interest" in f]
    return {"funding": funding, "macro": macro, "oi_points": oi_points}


def _feasible(data) -> str | None:
    for tf in TIMEFRAMES:
        if len(data.get(tf, [])) < MIN_BARS:
            return f"FEASIBILITY FAIL: {tf} has {len(data.get(tf, []))} bars < {MIN_BARS}"
    return None


def _window_doc(data) -> dict:
    out = {}
    for tf in TIMEFRAMES:
        cs = data.get(tf, [])
        out[tf] = {"bars": len(cs), "sha": _sha(cs) if cs else None}
    return out


def _register(args) -> int:
    data = _load_timeframes(args.symbol, args.start_ms, args.end_ms, args.cache_dir)
    prereg = {
        "lane": "btc_long_short_tournament",
        "asof": datetime.now(timezone.utc).isoformat(),
        "timeframes": list(TIMEFRAMES),
        "n_trials": len(all_configs(list(TIMEFRAMES))),
        "grid": config_doc(list(TIMEFRAMES)),
        "windows": {
            "train": [args.start_ms, args.start_ms + int((args.end_ms - args.start_ms) * 0.6)],
            "validate": [args.start_ms + int((args.end_ms - args.start_ms) * 0.6),
                         args.start_ms + int((args.end_ms - args.start_ms) * 0.8)],
            "sealed": [args.start_ms + int((args.end_ms - args.start_ms) * 0.8),
                       args.end_ms],
        },
        "gate": ("train practical bar (PF>=1.15, exp>0, n>=30, |maxDD|<=30R, "
                 "+5bps cost-stress, 2x and 3x multiplicative cost gates, outlier, "
                 "recent, island) + train twin beat -> freeze; validate/sealed "
                 "practical bar + 2x/3x cost gates, same expectancy sign, twin beat on both"),
        "data_fingerprint": _window_doc(data),
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    data = _load_timeframes(args.symbol, args.start_ms, args.end_ms, args.cache_dir)
    fail = _feasible(data)
    if fail:
        print(fail)
        return 2
    ctx = _load_context(args.start_ms, args.end_ms, args.cache_dir)
    train_by_tf = {tf: _split_60_20_20(data[tf])[0] for tf in TIMEFRAMES}
    rows = run_explore(all_configs(list(TIMEFRAMES)), train_by_tf,
                       context_by_tf={tf: ctx for tf in TIMEFRAMES})
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _select(args) -> int:
    data = _load_timeframes(args.symbol, args.start_ms, args.end_ms, args.cache_dir)
    fail = _feasible(data)
    if fail:
        print(fail)
        return 2
    ctx = _load_context(args.start_ms, args.end_ms, args.cache_dir)
    train_by_tf = {tf: _split_60_20_20(data[tf])[0] for tf in TIMEFRAMES}
    rows = run_explore(all_configs(list(TIMEFRAMES)), train_by_tf,
                       context_by_tf={tf: ctx for tf in TIMEFRAMES})
    survivors = select(rows, train_by_tf, context_by_tf={tf: ctx for tf in TIMEFRAMES})
    frozen = freeze_candidates(survivors)
    _write_json(Path(args.out_dir) / "frozen_candidates.json", frozen)
    return 0


def _validate(args) -> int:
    frozen_path = Path(args.out_dir) / "frozen_candidates.json"
    if not frozen_path.exists():
        print(f"no frozen_candidates.json in {args.out_dir}; run --select first")
        return 3
    frozen = json.loads(frozen_path.read_text())
    data = _load_timeframes(args.symbol, args.start_ms, args.end_ms, args.cache_dir)
    fail = _feasible(data)
    if fail:
        print(fail)
        return 2
    ctx = _load_context(args.start_ms, args.end_ms, args.cache_dir)
    train_by_tf, validate_by_tf, sealed_by_tf = {}, {}, {}
    for tf in TIMEFRAMES:
        tr, va, se = _split_60_20_20(data[tf])
        train_by_tf[tf], validate_by_tf[tf], sealed_by_tf[tf] = tr, va, se
    rows = validate_all(
        frozen, train_by_tf, validate_by_tf, sealed_by_tf,
        context_validate_by_tf={tf: ctx for tf in TIMEFRAMES},
        context_sealed_by_tf={tf: ctx for tf in TIMEFRAMES},
        context_train_by_tf={tf: ctx for tf in TIMEFRAMES},
    )
    result = {
        "lane": "btc_long_short_tournament",
        "asof": datetime.now(timezone.utc).isoformat(),
        "verdict": "paper_candidate" if any(r["verdict"] == "paper_candidate" for r in rows)
        else "negative",
        "rows": rows,
        "data_fingerprint": _window_doc(data),
    }
    _write_json(Path(args.out_dir) / "RESULT.json", result)
    data_shas = {tf: fp["sha"] for tf, fp in result["data_fingerprint"].items()}
    (Path(args.out_dir) / "FINDINGS.md").write_text(
        render_findings(rows, result["asof"], data_shas))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="ls-tournament")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--register", action="store_true")
    g.add_argument("--explore", action="store_true")
    g.add_argument("--select", action="store_true")
    g.add_argument("--validate", action="store_true")
    p.add_argument("--symbol", default=SYMBOL)
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", required=True)
    return p


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
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
