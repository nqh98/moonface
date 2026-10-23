#!/usr/bin/env python3
"""Staged BTC breadth-internal timing CLI (paper-only)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import _load, _sha, split_60_20_20, universe_covers_train  # noqa: E402
from moonface.research.breadth_internal.evaluate import evaluate_spec  # noqa: E402
from moonface.research.breadth_internal.grid import all_specs  # noqa: E402
from moonface.kernel.power_harness import bonferroni_level, judge_signal  # noqa: E402

SYMBOL = "BTCUSDT"
TF = "4h"
MIN_BARS = 300
_S1_XCHECK = {
    "validate_exp": 0.215,
    "sealed_exp": 0.212,
    "validate_n": 10,
    "sealed_n": 13,
}


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


def _window_bounds(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    train_end = args.start_ms + int(span * 0.6)
    validate_end = args.start_ms + int(span * 0.8)
    return {
        "train": [args.start_ms, train_end],
        "validate": [train_end, validate_end],
        "sealed": [validate_end, args.end_ms],
    }


def _feasible(btc) -> bool:
    return len(btc) >= MIN_BARS


def _register(args) -> int:
    btc, _, _ = _load(args)
    specs = all_specs()
    prereg = {
        "lane": "btc_breadth_internal_v2",
        "lane_description": (
            "Frozen internal breadth research lane with train/explore then one-shot "
            "validate over the holdout."
        ),
        "asof": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "timeframe": TF,
        "k_signals": len(specs),
        "bonferroni_level": bonferroni_level(len(specs)),
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": _window_bounds(args),
        "gate": (
            "train explore on the frozen grid, then validate once with pooled "
            "validate+sealed records judged by pooled practical + cost + bootstrap "
            "significance"
        ),
        "specs": [_spec_doc(spec) for spec in specs],
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
        print(
            "FEASIBILITY FAIL: universe daily history does not cover the train "
            "window (stale/short daily cache?). Refetch daily klines for the full "
            "registration window before running."
        )
        return 2

    rows = []
    for spec in all_specs():
        out = evaluate_spec(daily, train, spec, is_member=is_member)
        rows.append({"key": spec.key, "metrics": out["metrics"]})
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _xcheck_ok(validate: dict, sealed: dict) -> bool:
    tol = 0.01
    checks = [
        (validate["metrics"]["expectancy_r"], _S1_XCHECK["validate_exp"]),
        (sealed["metrics"]["expectancy_r"], _S1_XCHECK["sealed_exp"]),
        (validate["metrics"]["trade_count"], _S1_XCHECK["validate_n"]),
        (sealed["metrics"]["trade_count"], _S1_XCHECK["sealed_n"]),
    ]
    for got, exp in checks:
        if isinstance(exp, float):
            if abs(got - exp) > tol:
                return False
        elif got != exp:
            return False
    return True


def _forward_registration_doc(spec: dict, row: dict, out_dir: Path) -> None:
    lines = [
        f"# {spec['key'].upper()} Forward Paper Registration (frozen)",
        "",
        "Pre-registers the forward paper continuation for a frozen internal breadth "
        "spec that met the forward-candidate verdict on the unopened holdout.",
        "",
        "## Frozen spec",
        f"- key: `{spec['key']}`",
        f"- builder: `{spec['builder']}`",
        f"- params: `{spec['params']}`",
        f"- exit: `{spec['exit_name']}` `{spec['exit_params']}`",
        f"- h: `{spec['h']}`",
        "",
        "## Validation result",
        f"- verdict: `{row['verdict']}`",
        f"- validate expectation: `{row['validate']['metrics']['expectancy_r']}`",
        f"- sealed expectation: `{row['sealed']['metrics']['expectancy_r']}`",
        f"- pooled expectation: `{row['pooled']['expectancy_r']}`",
        "",
        "## Honest caveat",
        "Paper-only. Forward registration does not authorize live capital or modify "
        "the frozen breadth registry.",
    ]
    (out_dir / f"{spec['key'].upper()}_FORWARD_REGISTRATION.md").write_text(
        "\n".join(lines) + "\n"
    )


def _validate(args) -> int:
    btc, daily, is_member = _load(args)
    if not _feasible(btc):
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2

    train, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        print(
            "FEASIBILITY FAIL: universe daily history does not cover the validate "
            "window (stale/short daily cache?). Refetch daily klines for the full "
            "registration window before running."
        )
        return 2

    specs = all_specs()
    result_rows: list[dict] = []
    breadth_thrust_validate: dict | None = None
    breadth_thrust_sealed: dict | None = None

    for spec in specs:
        validate = evaluate_spec(daily, val, spec, is_member=is_member)
        sealed = evaluate_spec(daily, seal, spec, is_member=is_member)
        judge = judge_signal(
            validate["metrics"],
            sealed["metrics"],
            validate["records"] + sealed["records"],
            len(specs),
        )
        row = {
            "key": spec.key,
            "spec": _spec_doc(spec),
            "validate": validate,
            "sealed": sealed,
            "pooled": judge["pooled"],
            "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"],
            "same_sign": judge["same_sign"],
            "practical": judge["practical"],
            "cost": judge["cost"],
            "significant": judge["significant"],
            "verdict": judge["verdict"],
        }
        result_rows.append(row)
        if spec.key == "breadth_thrust":
            breadth_thrust_validate = validate
            breadth_thrust_sealed = sealed

    if any(row["verdict"] == "paper_candidate" for row in result_rows):
        verdict = "paper_candidate"
    elif any(row["verdict"] == "forward_candidate" for row in result_rows):
        verdict = "forward_candidate"
    else:
        verdict = "negative"

    s1_xcheck_ok = bool(
        breadth_thrust_validate
        and breadth_thrust_sealed
        and _xcheck_ok(breadth_thrust_validate, breadth_thrust_sealed)
    )

    asof = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir)
    result_doc = {
        "lane": "btc_breadth_internal_v2",
        "asof": asof,
        "symbol": SYMBOL,
        "timeframe": TF,
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": {
            "train": [args.start_ms, args.start_ms + int((args.end_ms - args.start_ms) * 0.6)],
            "validate": [args.start_ms + int((args.end_ms - args.start_ms) * 0.6),
                          args.start_ms + int((args.end_ms - args.start_ms) * 0.8)],
            "sealed": [args.start_ms + int((args.end_ms - args.start_ms) * 0.8), args.end_ms],
        },
        "bonferroni_alpha": bonferroni_level(len(specs)),
        "s1_xcheck": _S1_XCHECK,
        "s1_xcheck_ok": s1_xcheck_ok,
        "verdict": verdict,
        "rows": result_rows,
    }
    _write_json(out_dir / "RESULT.json", result_doc)

    lines = [
        "# BTC Breadth Internal v2",
        "",
        f"## Verdict: {verdict.upper() if verdict != 'negative' else 'NEGATIVE'}",
        "",
        f"- asof: {asof}",
        f"- data_sha: {result_doc['btc_sha']}",
        f"- bonferroni_alpha: {result_doc['bonferroni_alpha']}",
        f"- s1_xcheck_ok: {s1_xcheck_ok}",
        "",
        "| signal | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in result_rows:
        lines.append(
            f"| {row['key']} | {row['validate']['metrics']['expectancy_r']:.3f} | "
            f"{row['sealed']['metrics']['expectancy_r']:.3f} | "
            f"{row['pooled']['trade_count']} | {row['pooled']['expectancy_r']:.3f} | "
            f"{row['boot_lo']:.3f} | {row['p_le_zero']:.4f} | {row['verdict']} |"
        )
    lines.append(
        "\nPaper-only, BTC futures only. forward_candidate at n<30 is the expected "
        "underpowered outcome, not a failure.\n"
    )
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))

    for row in result_rows:
        if row["verdict"] == "forward_candidate":
            _forward_registration_doc(row["spec"], row, out_dir)

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth-internal")
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
