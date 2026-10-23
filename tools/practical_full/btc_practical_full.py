#!/usr/bin/env python3
"""BTC Practical FULL re-evaluation CLI — DSR-free practical bar over ALL price
families (old + new mechanisms) with a train(Explore)->holdout(Validate+Sealed)
discipline and the user's 2x/3x multiplicative cost gate.

Staged so the Explore/Validate/Sealed split is enforced structurally:
  --register : freeze PREREGISTRATION.md (grid/splits/gates) — commit before --explore.
  --explore  : stage 1 wide search on the EXPLORE slice -> explore_leaderboard.json.
  --select   : stage 2 selection (+2x/3x cost) -> frozen_candidates.json — commit first.
  --validate : stage 3+4 dual replication on VALIDATE+SEALED -> RESULT.md + result.json.

Free Binance OHLCV only. PAPER ONLY — promotes nothing to live, and never reads
or writes the deploy Donchian config, any promotion config, or the live journal.
DSR is REPORTED for transparency, never a gate. Reuses the tested practical
explore/select internals; only the comprehensive grid + cost-multiple gate are new."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.practical_full import grid  # noqa: E402
from moonface.research.practical_full.select_full import select_full  # noqa: E402
from moonface.research.practical_full.validate_full import validate_all_full  # noqa: E402
from moonface.research.practical.explore import run_explore  # noqa: E402
from moonface.research.practical.pipeline import (freeze_candidates,  # noqa: E402
                                                  to_leaderboard)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

TIMEFRAMES = ["2h", "4h"]   # fast comprehensive zone; btcspec's best near-miss was 2h
MIN_BARS = 300              # a timeframe below this cannot support a 60/20/20 split


def _grid_configs():
    return grid.all_configs(TIMEFRAMES)


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


def _explore_by_tf(data):
    return {tf: _split_60_20_20(data[tf])[0] for tf in TIMEFRAMES}


def _feasible(data) -> str | None:
    for tf in TIMEFRAMES:
        if len(data.get(tf, [])) < MIN_BARS:
            return f"FEASIBILITY FAIL: {tf} has {len(data.get(tf, []))} bars < {MIN_BARS}"
    return None


def _write_prereg(out: Path, data: dict) -> None:
    cfgs = _grid_configs()
    fams = sorted({c.family for c in cfgs})
    exits = sorted({c.exit_name for c in cfgs})
    lines = [
        "# BTC Practical FULL Re-Evaluation — PREREGISTRATION (frozen)", "",
        f"- asof: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframes: {', '.join(TIMEFRAMES)}",
        f"- configs (reported DSR n_trials): {len(cfgs)}",
        f"- families: {', '.join(fams)}",
        f"- exits: {', '.join(exits)}",
        "- split: chronological Explore/Validate/Sealed 60/20/20 per timeframe "
        "(Sealed = most-recent holdout)",
        "- selection gates: net-R>0, PF>=1.15, expectancy>0, |DD|<=30R@f=0.01, "
        "trades>=30, parameter-island, outlier-dependence, +5bps cost-stress, "
        "recent-period, AND 2x AND 3x multiplicative cost",
        "- accept: dual replication on Validate AND Sealed (same thresholds + same "
        "sign + 2x/3x cost on both); DSR reported, NOT a gate; output PAPER ONLY",
        "- isolation: Donchian / promotion / journal untouched; EXIT_REGISTRY unchanged",
        "", "## Per-timeframe data fingerprint", "",
        "| timeframe | bars | data_sha |", "|---|---|---|",
    ]
    for tf in TIMEFRAMES:
        cs = data.get(tf, [])
        lines.append(f"| {tf} | {len(cs)} | {_sha(cs) if cs else '-'} |")
    out.write_text("\n".join(lines) + "\n")


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def _render_result(result_rows, asof, shas) -> str:
    any_accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    overall = ("PAPER CANDIDATE(S) FOUND (PAPER ONLY — not live)"
               if any_accept else "NEGATIVE")
    sha_s = ", ".join(f"{tf}={s}" for tf, s in sorted(shas.items()))
    head = (f"# BTC Practical FULL Re-Evaluation\n\n## Verdict: {overall}\n\n"
            f"- asof: {asof}\n- data_sha: {sha_s}\n"
            f"- gate: explore(wide) -> selection(+2x/3x cost) -> dual replication "
            f"(validate AND sealed); DSR reported, NOT gated\n\n"
            "| cell | tf | family | dsr | val_pf | val_exp | seal_pf | seal_exp | "
            "v_2x | v_3x | s_2x | s_3x | verdict |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for r in result_rows:
        v, s = r.get("validate", {}), r.get("sealed", {})
        lines.append(
            f"| {r['label']} | {r['timeframe']} | {r['family']} | {_f(r.get('dsr'))} | "
            f"{_f(v.get('profit_factor'))} | {_f(v.get('expectancy_r'))} | "
            f"{_f(s.get('profit_factor'))} | {_f(s.get('expectancy_r'))} | "
            f"{v.get('cost_2x_ok')} | {v.get('cost_3x_ok')} | "
            f"{s.get('cost_2x_ok')} | {s.get('cost_3x_ok')} | {r['verdict']} |")
    caveat = ("A NEGATIVE is the expected, valid outcome. Any accepted candidate is "
              "a single-asset BTC PAPER ONLY signal — it does NOT authorize live "
              "capital or automatic execution, must get its own frozen paper-forward "
              "protocol, and never inherits the live/Donchian slot. The frozen 4h "
              "Donchian Slice-3 strategy is untouched by this lane.")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC practical FULL re-evaluation")
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
        rows = run_explore(_grid_configs(), _explore_by_tf(data))
        (out / "explore_leaderboard.json").write_text(json.dumps(rows, indent=2))
        print(f"explored {len(rows)} configs -> {out}/explore_leaderboard.json")
        return 0

    if args.select:
        explore_by_tf = _explore_by_tf(data)
        rows = run_explore(_grid_configs(), explore_by_tf)
        survivors = select_full(rows, explore_by_tf)
        frozen = freeze_candidates(survivors)
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
        _e, v, s = _split_60_20_20(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
        shas[tf] = _sha(data[tf])
    result_rows = validate_all_full(frozen, validate_by_tf, sealed_by_tf)
    asof = datetime.now(timezone.utc).isoformat()
    (out / "RESULT.md").write_text(_render_result(result_rows, asof, shas))
    (out / "result.json").write_text(json.dumps(to_leaderboard(result_rows), indent=2))
    accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    print(f"verdict: {'PAPER CANDIDATE(S)' if accept else 'NEGATIVE'} -> {out}/RESULT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
