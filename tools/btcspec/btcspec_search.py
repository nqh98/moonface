#!/usr/bin/env python3
"""BTC-Specialized Practical Signal Optimization CLI — Slice 1 (2h, 4h trend+breakout).

Staged so the Explore/Validate/Sealed split is enforced structurally:
  --register : freeze PREREGISTRATION.md (grid/splits/gates) — commit before --explore.
  --explore  : stage 1 wide search on the EXPLORE slice -> explore_leaderboard.json.
  --select   : stage 2 island+top-K -> frozen_candidates.json — commit before --validate.
  --validate : hybrid walk-forward + single sealed-tail on VALIDATE+SEALED -> RESULT.md.

Free Binance BTCUSDT OHLCV only. PAPER ONLY — promotes nothing to live, and never reads
or writes any deploy/promotion config or the live signal journal."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.btcspec.exits_scaled import (TF_MAX_HOLD_BARS,  # noqa: E402
                                                    TIMEFRAMES)
from moonface.research.btcspec.families import all_explore_configs  # noqa: E402
from moonface.research.btcspec.explore import run_explore  # noqa: E402
from moonface.research.btcspec.select import TOP_K, select  # noqa: E402
from moonface.research.btcspec.validate import (ROBUST_FLOOR,  # noqa: E402
                                                TRADE_FLOOR, validate_all)
from moonface.research.btcspec.pipeline import (freeze_candidates,  # noqa: E402
                                                render_result, to_leaderboard)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

MIN_BARS = 300  # a timeframe below this cannot support a credible 55/25/20 split


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_55_25_20(candles):
    n = len(candles)
    a, b = int(0.55 * n), int(0.80 * n)
    return candles[:a], candles[a:b], candles[b:]


def _load_timeframes(symbol, start_ms, end_ms, cache_dir) -> dict:
    return {tf: fetch_perp_candles(symbol, tf, start_ms, end_ms, cache_dir)
            for tf in TIMEFRAMES}


def _explore_by_tf(data):
    return {tf: _split_55_25_20(data[tf])[0] for tf in TIMEFRAMES}


def _feasible(data) -> str | None:
    for tf in TIMEFRAMES:
        if len(data.get(tf, [])) < MIN_BARS:
            return f"FEASIBILITY FAIL: {tf} has {len(data.get(tf, []))} bars < {MIN_BARS}"
    return None


def _write_prereg(out: Path, data: dict) -> None:
    cfgs = all_explore_configs()
    lines = [
        "# BTC-Specialized Signal Optimization — Slice 1 PREREGISTRATION (frozen)", "",
        f"- asof: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframes (slice 1): {', '.join(TIMEFRAMES)}",
        f"- pooled n_trials (reported DSR): {len(cfgs)}",
        "- split: chronological Explore/Validate/Sealed 55/25/20 per timeframe",
        f"- TF max-hold bars: {TF_MAX_HOLD_BARS}",
        f"- selection: parameter-island filter + top-{TOP_K}/family by net total R",
        f"- validation: walk-forward robust_frac>={ROBUST_FLOOR} on VALIDATE, then the "
        f"single best (by validate net R) opened ONCE on SEALED under the locked econ "
        f"bar (PF>=1.2/exp>=0.05R/MAR>=0.5/DD<=30R@f=0.01/robust>=0.60) + positive net R "
        f"both segments + trade-count floor {TRADE_FLOOR} + outlier(top-1/top-3) + "
        f"+5bps cost-stress + recent-period",
        "- accept: every gate on clean OOS -> PAPER ONLY (own forward protocol; never "
        "the Donchian slot; live disabled)",
        "- DSR reported, NOT a gate; isolation: Donchian/promotion/journal untouched; "
        "EXIT_REGISTRY unchanged",
        "", "## Per-timeframe data fingerprint", "",
        "| timeframe | bars | data_sha |", "|---|---|---|",
    ]
    for tf in TIMEFRAMES:
        cs = data.get(tf, [])
        lines.append(f"| {tf} | {len(cs)} | {_sha(cs) if cs else '-'} |")
    out.write_text("\n".join(lines) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="BTC-Specialized signal optimization (Slice 1: 2h, 4h)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--explore", action="store_true")
    mode.add_argument("--select", action="store_true")
    mode.add_argument("--validate", action="store_true")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--cache-dir", default=".backtest_cache")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = _load_timeframes(args.symbol, args.start_ms, args.end_ms, args.cache_dir)

    if args.register:
        _write_prereg(out / "PREREGISTRATION.md", data)
        print(f"registered -> {out}/PREREGISTRATION.md (commit before --explore)")
        return 0

    fail = _feasible(data)
    if fail:
        print(fail)
        return 2

    if args.explore:
        rows = run_explore(all_explore_configs(), _explore_by_tf(data))
        (out / "explore_leaderboard.json").write_text(json.dumps(rows, indent=2))
        print(f"explored {len(rows)} configs -> {out}/explore_leaderboard.json")
        return 0

    if args.select:
        rows = run_explore(all_explore_configs(), _explore_by_tf(data))
        frozen = freeze_candidates(select(rows))
        (out / "frozen_candidates.json").write_text(json.dumps(frozen, indent=2))
        print(f"selected {len(frozen)} survivors -> {out}/frozen_candidates.json "
              f"(commit before --validate)")
        return 0

    # --validate
    frozen_path = out / "frozen_candidates.json"
    if not frozen_path.exists():
        print(f"no frozen_candidates.json in {out}; run --select first")
        return 3
    frozen = json.loads(frozen_path.read_text())
    validate_by_tf, sealed_by_tf, shas = {}, {}, {}
    for tf in TIMEFRAMES:
        _e, v, s = _split_55_25_20(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
        shas[tf] = _sha(data[tf])
    result_rows = validate_all(frozen, validate_by_tf, sealed_by_tf)
    asof = datetime.now(timezone.utc).isoformat()
    (out / "RESULT.md").write_text(render_result(result_rows, asof, shas))
    (out / "result.json").write_text(json.dumps(to_leaderboard(result_rows), indent=2))
    accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    print(f"verdict: {'PAPER CANDIDATE(S)' if accept else 'NEGATIVE'} -> {out}/RESULT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
