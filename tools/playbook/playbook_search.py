#!/usr/bin/env python3
"""BTC Multi-Timeframe Trend Playbook — signal-engine search CLI (1h/2h/4h).

Staged so Explore/Validate/Sealed is enforced structurally:
  --register : freeze PREREGISTRATION.md — commit before --explore.
  --explore  : stage 1 on the EXPLORE segment -> explore_leaderboard.json.
  --select   : stage 2 selection -> frozen_candidates.json — commit before --validate.
  --validate : stage 3+4 dual replication on VALIDATE+SEALED -> RESULT.md + result.json.

Free Binance BTCUSDT OHLCV only. PAPER ONLY — never reads/writes the deploy
Donchian config, any promotion config, or the live signal journal."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.playbook.families import all_playbook_configs, GRID_SIZE  # noqa: E402
from moonface.research.playbook.mtf import MTFView  # noqa: E402
from moonface.research.playbook.explore import run_explore  # noqa: E402
from moonface.research.playbook.select import select  # noqa: E402
from moonface.research.playbook.validate import validate_all  # noqa: E402
from moonface.research.playbook.pipeline import freeze_survivors, render_result  # noqa: E402
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

TIMEFRAMES = ("1h", "2h", "4h")
MIN_BARS = 300


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_60_20_20(candles):
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    return candles[:a], candles[a:b], candles[b:]


def _slice(data, which):
    idx = {"explore": 0, "validate": 1, "sealed": 2}[which]
    return {tf: _split_60_20_20(data[tf])[idx] for tf in TIMEFRAMES}


def _segment_view(data, which) -> MTFView:
    seg = _slice(data, which)
    return MTFView.build(seg["1h"], seg["2h"], seg["4h"])


def _load(symbol, start_ms, end_ms, cache_dir) -> dict:
    return {tf: fetch_perp_candles(symbol, tf, start_ms, end_ms, cache_dir)
            for tf in TIMEFRAMES}


def _feasible(data) -> str | None:
    for tf in TIMEFRAMES:
        if len(data.get(tf, [])) < MIN_BARS:
            return f"FEASIBILITY FAIL: {tf} has {len(data.get(tf, []))} bars < {MIN_BARS}"
    return None


def _prereg_text(data: dict) -> str:
    lines = [
        "# BTC Multi-Timeframe Trend Playbook — PREREGISTRATION (frozen)", "",
        f"- asof: {datetime.now(timezone.utc).isoformat()}",
        "- timeframes: 4h regime / 2h confirm / 1h trigger",
        f"- n_trials (reported DSR, NOT gated): {GRID_SIZE}",
        "- split: chronological Explore/Validate/Sealed 60/20/20 per timeframe",
        f"- selection gates: PF>={PF_FLOOR}, expectancy>0, |DD|<={MAX_DD_R}R@f=0.01, "
        f"trades>={MIN_TRADES}, outlier-dependence, +5bps cost-stress, recent-period",
        "- accept: dual replication on Validate AND Sealed (same thresholds + same "
        "expectancy sign); DSR reported, NOT a gate; output PAPER ONLY",
        "- isolation: Donchian Slice-3 / promotion / journal untouched; "
        "EXIT_REGISTRY unchanged (lane adds no executable exit)",
        "", "## Frozen configs", "", "| label | exit |", "|---|---|"]
    for c in all_playbook_configs():
        lines.append(f"| {c.label} | {c.exit_name} |")
    lines += ["", "## Per-timeframe data fingerprint", "",
              "| timeframe | bars | data_sha |", "|---|---|---|"]
    for tf in TIMEFRAMES:
        cs = data.get(tf, [])
        lines.append(f"| {tf} | {len(cs)} | {_sha(cs) if cs else '-'} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC playbook signal-engine search")
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
    data = _load(args.symbol, args.start_ms, args.end_ms, args.cache_dir)

    if args.register:
        (out / "PREREGISTRATION.md").write_text(_prereg_text(data))
        print(f"registered -> {out}/PREREGISTRATION.md (commit before --explore)")
        return 0

    fail = _feasible(data)
    if fail:
        print(fail)
        return 2

    configs = all_playbook_configs()
    by_label = {c.label: c for c in configs}

    if args.explore:
        rows = run_explore(configs, _segment_view(data, "explore"))
        slim = [{k: r[k] for k in ("label", "dsr", "metrics")} for r in rows]
        (out / "explore_leaderboard.json").write_text(json.dumps(slim, indent=2))
        print(f"explored {len(rows)} configs -> {out}/explore_leaderboard.json")
        return 0

    if args.select:
        ev = _segment_view(data, "explore")
        rows = run_explore(configs, ev)
        survivors = select(rows, ev, by_label)
        (out / "frozen_candidates.json").write_text(
            json.dumps(freeze_survivors(survivors), indent=2))
        print(f"selected {len(survivors)} survivors -> {out}/frozen_candidates.json "
              f"(commit before --validate)")
        return 0

    # --validate
    frozen_path = out / "frozen_candidates.json"
    if not frozen_path.exists():
        print(f"no frozen_candidates.json in {out}; run --select first")
        return 3
    labels = json.loads(frozen_path.read_text())
    frozen = [by_label[lbl] for lbl in labels]
    vview = _segment_view(data, "validate")
    sview = _segment_view(data, "sealed")
    result_rows = validate_all(frozen, vview, sview)
    asof = datetime.now(timezone.utc).isoformat()
    shas = {tf: _sha(data[tf]) for tf in TIMEFRAMES}
    (out / "RESULT.md").write_text(render_result(result_rows, asof, shas))
    (out / "result.json").write_text(json.dumps(result_rows, indent=2))
    accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    print(f"verdict: {'PAPER CANDIDATE(S)' if accept else 'NEGATIVE'} -> {out}/RESULT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
