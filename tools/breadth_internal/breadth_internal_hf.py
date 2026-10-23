#!/usr/bin/env python3
"""Staged BTC high-frequency breadth-internal timing CLI (Lane 2, paper-only)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import _load, _sha, split_60_20_20, universe_covers_train  # noqa: E402
from moonface.research.breadth.signals import entries_from_state  # noqa: E402
from moonface.research.breadth_internal.hf_evaluate import (  # noqa: E402
    evaluate_hf_spec,
    hf_cell_entries,
)
from moonface.research.breadth_internal.hf_grid import BLOCK_LEN, hf_specs  # noqa: E402
from moonface.research.breadth_internal.hf_signals import (  # noqa: E402
    breadth_oscillator_state,
)
from moonface.kernel.power_harness import (  # noqa: E402
    bonferroni_level,
    bootstrap_expectancy,
    judge_signal,
    one_sided_lower,
)

SYMBOL = "BTCUSDT"
TF = "4h"
MIN_BARS = 300


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _spec_doc(spec) -> dict:
    return {
        "key": spec.key,
        "builder": spec.builder,
        "params": dict(spec.params),
        "exit_name": spec.exit_name,
        "exit_params": dict(spec.exit_params),
        "h": spec.h,
    }


def _windows(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    return {
        "train": [args.start_ms, args.start_ms + int(span * 0.6)],
        "validate": [args.start_ms + int(span * 0.6), args.start_ms + int(span * 0.8)],
        "sealed": [args.start_ms + int(span * 0.8), args.end_ms],
    }


def _overlap_xcheck(daily, btc, is_member) -> bool:
    """Overlapping oscillator entries must outnumber the transition mapping."""
    osc = hf_specs()[0]
    state = breadth_oscillator_state(
        daily, int(osc.params["window"]), osc.params["z_in"],
        int(osc.params["base_period"]), is_member=is_member)
    overlap = hf_cell_entries(daily, btc, osc, is_member)
    transition = entries_from_state(btc, state, osc.h)
    return len(overlap) > len(transition)


def _block_xcheck(records) -> bool:
    """Block bootstrap CI must differ from the i.i.d. CI on the pooled records."""
    net_rs = [r["net_r"] for r in records]
    alpha = bonferroni_level(len(hf_specs()))
    means_iid, _ = bootstrap_expectancy(net_rs, n_resamples=20_000, seed=20260628)
    means_blk, _ = bootstrap_expectancy(
        net_rs, n_resamples=20_000, seed=20260628, block=True, block_len=BLOCK_LEN)
    return one_sided_lower(means_iid, alpha) != one_sided_lower(means_blk, alpha)


def _feasible(btc) -> bool:
    return len(btc) >= MIN_BARS


def _register(args) -> int:
    btc, _, _ = _load(args)
    specs = hf_specs()
    prereg = {
        "lane": "btc_breadth_internal_hf",
        "lane_description": (
            "Lane 2: high-frequency overlapping breadth signals judged with the "
            "moving-block bootstrap (block_len derived from h/bars_per_day)."),
        "asof": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "timeframe": TF,
        "k_signals": len(specs),
        "bonferroni_level": bonferroni_level(len(specs)),
        "block_len": BLOCK_LEN,
        "block_len_derivation": "h / bars_per_day = 48 / 6 = 8 (derived, not tuned)",
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": _windows(args),
        "gate": (
            "train explore on the frozen grid, then validate once; per signal "
            "judge pooled validate+sealed records with the block bootstrap "
            "(block_len=8) at alpha/K=0.0167 plus same-sign + practical + 2x/3x "
            "cost; forward_candidate if OOS-positive but not significant"),
        "specs": [_spec_doc(s) for s in specs],
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    btc, daily, is_member = _load(args)
    if not _feasible(btc):
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2
    train = split_60_20_20(btc)[0]
    if not universe_covers_train(daily, is_member, train):
        print("FEASIBILITY FAIL: universe daily history does not cover train.")
        return 2
    rows = [{"key": s.key, "metrics": evaluate_hf_spec(daily, train, s, is_member)["metrics"]}
            for s in hf_specs()]
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _forward_doc(spec: dict, row: dict, out_dir: Path) -> None:
    lines = [
        f"# {spec['key'].upper()} Forward Paper Registration (frozen, Lane 2)",
        "",
        "Forward continuation for a frozen high-frequency breadth spec that met "
        "the forward-candidate verdict on the unopened holdout.",
        "",
        "## Frozen spec",
        f"- key: `{spec['key']}`  builder: `{spec['builder']}`",
        f"- params: `{spec['params']}`  block_len: `8`",
        f"- exit: `{spec['exit_name']}` `{spec['exit_params']}`  h: `{spec['h']}`",
        "",
        "## Validation result",
        f"- verdict: `{row['verdict']}`  pooled exp: `{row['pooled']['expectancy_r']}`",
        f"- boot_lo: `{row['boot_lo']}`  p_le0: `{row['p_le_zero']}`",
        "",
        "## Resolution rule",
        "CONFIRM iff forward-only pooled n>=30 AND bootstrap CI lower bound > 0 "
        "AND forward-only exp > 0; REFUTE / early-kill at cumulative -30R.",
        "",
        "Paper-only. Does not authorize live capital or modify any registry.",
    ]
    (out_dir / f"{spec['key'].upper()}_FORWARD_REGISTRATION.md").write_text(
        "\n".join(lines) + "\n")


def _validate(args) -> int:
    btc, daily, is_member = _load(args)
    if not _feasible(btc):
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2
    train, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        print("FEASIBILITY FAIL: universe daily history does not cover validate.")
        return 2

    specs = hf_specs()
    rows = []
    for spec in specs:
        validate = evaluate_hf_spec(daily, val, spec, is_member)
        sealed = evaluate_hf_spec(daily, seal, spec, is_member)
        judge = judge_signal(
            validate["metrics"], sealed["metrics"],
            validate["records"] + sealed["records"], len(specs),
            block=True, block_len=BLOCK_LEN)
        rows.append({
            "key": spec.key, "spec": _spec_doc(spec),
            "validate": validate, "sealed": sealed,
            "pooled": judge["pooled"], "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"], "same_sign": judge["same_sign"],
            "practical": judge["practical"], "cost": judge["cost"],
            "significant": judge["significant"], "verdict": judge["verdict"],
        })

    if any(r["verdict"] == "paper_candidate" for r in rows):
        verdict = "paper_candidate"
    elif any(r["verdict"] == "forward_candidate" for r in rows):
        verdict = "forward_candidate"
    else:
        verdict = "negative"

    overlap_ok = _overlap_xcheck(daily, val, is_member)
    pooled_first = rows[0]["validate"]["records"] + rows[0]["sealed"]["records"]
    block_ok = _block_xcheck(pooled_first) if pooled_first else False

    asof = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir)
    _write_json(out_dir / "RESULT.json", {
        "lane": "btc_breadth_internal_hf", "asof": asof,
        "symbol": SYMBOL, "timeframe": TF,
        "btc_bars": len(btc), "btc_sha": _sha(btc),
        "windows": _windows(args), "block_len": BLOCK_LEN,
        "bonferroni_alpha": bonferroni_level(len(specs)),
        "overlap_xcheck_ok": overlap_ok, "block_xcheck_ok": block_ok,
        "verdict": verdict, "rows": rows,
    })

    lines = [
        "# BTC Breadth Internal Lane 2 (high-frequency, block-bootstrap)",
        "",
        f"## Verdict: {verdict.upper() if verdict != 'negative' else 'NEGATIVE'}",
        "",
        f"- asof: {asof}  block_len: {BLOCK_LEN}",
        f"- overlap_xcheck_ok: {overlap_ok}  block_xcheck_ok: {block_ok}",
        f"- bonferroni_alpha: {bonferroni_level(len(specs))}",
        "",
        "| signal | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['key']} | {r['validate']['metrics']['expectancy_r']:.3f} | "
            f"{r['sealed']['metrics']['expectancy_r']:.3f} | "
            f"{r['pooled']['trade_count']} | {r['pooled']['expectancy_r']:.3f} | "
            f"{r['boot_lo']:.3f} | {r['p_le_zero']:.4f} | {r['verdict']} |")
    lines.append(
        "\nPaper-only, BTC futures only. Overlapping trades inflate n but not the "
        "effective sample; the block bootstrap keeps CIs honest.\n")
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))

    for r in rows:
        if r["verdict"] == "forward_candidate":
            _forward_doc(r["spec"], r, out_dir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth-internal-hf")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--explore", action="store_true")
    mode.add_argument("--validate", action="store_true")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", required=True)
    return p


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    if args.register:
        return _register(args)
    if args.explore:
        return _explore(args)
    if args.validate:
        return _validate(args)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
