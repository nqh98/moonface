#!/usr/bin/env python3
"""Staged BTC breadth-confirmation CLI (paper-only).

Confirms the frozen net_new_highs signal on DISJOINT volume-rank universe
slices (independent realizations) — never re-gates the top-20 discovery."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import (  # noqa: E402
    MIN_HISTORY_DAYS,
    REBALANCE_DAYS,
    VOL_DAYS,
    _load,
    _sha,
    split_60_20_20,
    universe_covers_train,
)
from moonface.research.breadth_confirm.evaluate import evaluate_slice_overlap  # noqa: E402
from moonface.research.breadth_confirm.grid import (  # noqa: E402
    BLOCK_LEN,
    DISCOVERY_SLICE,
    GATED_SLICES,
    K,
    net_new_highs_spec,
)
from moonface.research.breadth_confirm.universe_slice import slice_membership_fn  # noqa: E402
from moonface.research.breadth_internal.evaluate import evaluate_spec  # noqa: E402
from moonface.kernel.power_harness import bonferroni_level, judge_signal  # noqa: E402

SYMBOL = "BTCUSDT"
TF = "4h"
MIN_BARS = 300
_XCHECK = {"validate_exp": 0.5323, "sealed_exp": 0.2588, "validate_n": 34, "sealed_n": 32}


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _slice_membership(daily, slice_):
    return slice_membership_fn(
        daily, slice_[0], slice_[1], MIN_HISTORY_DAYS, VOL_DAYS, REBALANCE_DAYS
    )


def _window_bounds(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    t = args.start_ms + int(span * 0.6)
    v = args.start_ms + int(span * 0.8)
    return {"train": [args.start_ms, t], "validate": [t, v], "sealed": [v, args.end_ms]}


def _xcheck_ok(validate: dict, sealed: dict) -> bool:
    tol = 0.01
    checks = [
        (validate["metrics"]["expectancy_r"], _XCHECK["validate_exp"]),
        (sealed["metrics"]["expectancy_r"], _XCHECK["sealed_exp"]),
        (validate["metrics"]["trade_count"], _XCHECK["validate_n"]),
        (sealed["metrics"]["trade_count"], _XCHECK["sealed_n"]),
    ]
    for got, exp in checks:
        if isinstance(exp, float):
            if abs(got - exp) > tol:
                return False
        elif got != exp:
            return False
    return True


def _lane_verdict(rows: list[dict]) -> str:
    return "confirmed" if any(r["status"] == "confirmed" for r in rows) else "mechanism_unconfirmed"


def _register(args) -> int:
    btc, _, _ = _load(args)
    spec = net_new_highs_spec()
    prereg = {
        "lane": "btc_breadth_confirm",
        "lane_description": (
            "Independent-realization confirmation of the frozen net_new_highs signal "
            "on disjoint volume-rank universe slices. Top-20 is the discovery "
            "(x-checked, never gated)."
        ),
        "asof": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "timeframe": TF,
        "frozen_spec": {
            "key": spec.key,
            "builder": spec.builder,
            "params": dict(spec.params),
            "exit_name": spec.exit_name,
            "exit_params": dict(spec.exit_params),
            "h": spec.h,
        },
        "discovery_slice": list(DISCOVERY_SLICE),
        "gated_slices": [list(s) for s in GATED_SLICES],
        "k_gated": K,
        "block_len": BLOCK_LEN,
        "bonferroni_level": bonferroni_level(K),
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": _window_bounds(args),
        "gate": (
            "per disjoint slice: same-sign + practical + 2x/3x cost + one-sided "
            "block-bootstrap p_le0 < 0.025; lane confirmed iff >=1 gated slice passes; "
            "top-20 reported not gated"
        ),
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    btc, daily, _ = _load(args)
    if len(btc) < MIN_BARS:
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2
    train = split_60_20_20(btc)[0]
    spec = net_new_highs_spec()
    rows = []
    for slice_ in (DISCOVERY_SLICE, *GATED_SLICES):
        is_member = _slice_membership(daily, slice_)
        feasible = universe_covers_train(daily, is_member, train)
        metrics = (
            evaluate_slice_overlap(daily, train, spec, is_member=is_member)["metrics"]
            if feasible
            else None
        )
        rows.append({"slice": list(slice_), "feasible": feasible, "metrics": metrics})
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _validate(args) -> int:
    btc, daily, _ = _load(args)
    if len(btc) < MIN_BARS:
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2
    train, val, seal = split_60_20_20(btc)
    spec = net_new_highs_spec()

    # Discovery x-check on top-20, NON-overlap (reproduces v2 n=66), never gated.
    disc_member = _slice_membership(daily, DISCOVERY_SLICE)
    disc_validate = evaluate_spec(daily, val, spec, is_member=disc_member)
    disc_sealed = evaluate_spec(daily, seal, spec, is_member=disc_member)
    xcheck_ok = _xcheck_ok(disc_validate, disc_sealed)

    rows: list[dict] = []
    for slice_ in GATED_SLICES:
        is_member = _slice_membership(daily, slice_)
        if not universe_covers_train(daily, is_member, val):
            rows.append({"slice": list(slice_), "status": "infeasible"})
            continue
        validate = evaluate_slice_overlap(daily, val, spec, is_member=is_member)
        sealed = evaluate_slice_overlap(daily, seal, spec, is_member=is_member)
        judge = judge_signal(
            validate["metrics"],
            sealed["metrics"],
            validate["records"] + sealed["records"],
            K,
            block=True,
            block_len=BLOCK_LEN,
        )
        status = "confirmed" if judge["verdict"] == "paper_candidate" else "mechanism_unconfirmed"
        rows.append(
            {
                "slice": list(slice_),
                "status": status,
                "validate_exp": validate["metrics"]["expectancy_r"],
                "sealed_exp": sealed["metrics"]["expectancy_r"],
                "pooled": judge["pooled"],
                "boot_lo": judge["boot_lo"],
                "p_le_zero": judge["p_le_zero"],
                "same_sign": judge["same_sign"],
                "practical": judge["practical"],
                "cost": judge["cost"],
                "significant": judge["significant"],
            }
        )

    verdict = _lane_verdict(rows)
    asof = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir)
    result_doc = {
        "lane": "btc_breadth_confirm",
        "asof": asof,
        "symbol": SYMBOL,
        "timeframe": TF,
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": _window_bounds(args),
        "bonferroni_alpha": bonferroni_level(K),
        "block_len": BLOCK_LEN,
        "discovery_xcheck_ok": xcheck_ok,
        "discovery": {
            "validate_exp": disc_validate["metrics"]["expectancy_r"],
            "validate_n": disc_validate["metrics"]["trade_count"],
            "sealed_exp": disc_sealed["metrics"]["expectancy_r"],
            "sealed_n": disc_sealed["metrics"]["trade_count"],
        },
        "verdict": verdict,
        "rows": rows,
    }
    _write_json(out_dir / "RESULT.json", result_doc)

    lines = [
        "# BTC Breadth Confirm (net_new_highs on disjoint universes)",
        "",
        f"## Verdict: {verdict.upper()}",
        "",
        f"- asof: {asof}",
        f"- data_sha: {result_doc['btc_sha']}",
        f"- bonferroni_alpha: {result_doc['bonferroni_alpha']}",
        f"- discovery_xcheck_ok: {xcheck_ok}",
        "",
        "| slice | status | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] == "infeasible":
            lines.append(f"| {r['slice']} | infeasible | - | - | - | - | - | - |")
            continue
        lines.append(
            f"| {r['slice']} | {r['status']} | {r['validate_exp']:.3f} | "
            f"{r['sealed_exp']:.3f} | {r['pooled']['trade_count']} | "
            f"{r['pooled']['expectancy_r']:.3f} | {r['boot_lo']:.3f} | {r['p_le_zero']:.4f} |"
        )
    lines.append(
        "\nPaper-only, BTC futures only. Disjoint-slice confirmation cures the "
        "winner's-curse selection bias; the top-20 discovery is reported (x-check "
        f"ok={xcheck_ok}), never re-gated. mechanism_unconfirmed at thin-slice n is "
        "the expected underpowered outcome — resolution defers to forward time.\n"
    )
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth-confirm")
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
