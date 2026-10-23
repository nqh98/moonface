#!/usr/bin/env python3
"""Staged cross-asset confirmation CLI for the breadth-internal leads (paper-only).

Transfers the two never-killed breadth-internal leads (net_new_highs,
breadth_momentum) onto ETH/SOL as the traded leg — an independent-asset
robustness axis distinct from the disjoint-universe cure. The BTC breadth state
is byte-identical (BTC-excluded top-20); only the traded candle series changes.
The BTC discovery is anchor-x-checked per signal and never re-gated."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import (  # noqa: E402
    TF,
    _load,
    _sha,
    split_60_20_20,
    universe_covers_train,
)
from moonface.research.breadth_confirm.xasset_grid import ASSETS, K, lead_specs  # noqa: E402
from moonface.research.breadth_internal.evaluate import evaluate_spec  # noqa: E402
from moonface.research.breadth_internal.hf_evaluate import evaluate_hf_spec  # noqa: E402
from moonface.kernel.power_harness import bonferroni_level, judge_signal  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

MIN_BARS = 300

# Per-lead evaluator + bootstrap mode, matching how each lead was originally
# judged: net_new_highs is h=48 non-overlap (iid); breadth_momentum is the
# overlapping HF construction (moving-block bootstrap, block_len=8).
LEAD_EVAL = {
    "net_new_highs": (evaluate_spec, False, 1),
    "breadth_momentum": (evaluate_hf_spec, True, 8),
}

# BTC discovery anchors (reproduce the home-lane numbers before reading ETH/SOL).
ANCHOR = {
    "net_new_highs": {"val_exp": 0.5323, "seal_exp": 0.2588, "val_n": 34, "seal_n": 32},
    "breadth_momentum": {"val_exp": 0.1652, "seal_exp": 0.1424, "val_n": 327, "seal_n": 326},
}


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _window_bounds(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    t = args.start_ms + int(span * 0.6)
    v = args.start_ms + int(span * 0.8)
    return {"train": [args.start_ms, t], "validate": [t, v], "sealed": [v, args.end_ms]}


def _anchor_ok(key: str, validate: dict, sealed: dict) -> bool:
    a = ANCHOR[key]
    tol = 0.01
    pairs = [
        (validate["metrics"]["expectancy_r"], a["val_exp"], True),
        (sealed["metrics"]["expectancy_r"], a["seal_exp"], True),
        (validate["metrics"]["trade_count"], a["val_n"], False),
        (sealed["metrics"]["trade_count"], a["seal_n"], False),
    ]
    for got, exp, is_float in pairs:
        if is_float:
            if abs(got - exp) > tol:
                return False
        elif got != exp:
            return False
    return True


def _fetch_asset(args, symbol: str):
    return fetch_perp_candles(symbol, TF, args.start_ms, args.end_ms, args.cache_dir)


def _register(args) -> int:
    btc, _, _ = _load(args)
    specs = lead_specs()
    prereg = {
        "lane": "breadth_xasset_confirm",
        "lane_description": (
            "Cross-asset transfer confirmation of the two breadth-internal leads "
            "(net_new_highs, breadth_momentum) onto ETH/SOL as the traded leg. "
            "Breadth state byte-identical (BTC-excluded top-20); BTC discovery "
            "anchor-x-checked per signal, never re-gated."
        ),
        "asof": datetime.now(timezone.utc).isoformat(),
        "assets": list(ASSETS),
        "timeframe": TF,
        "frozen_leads": [
            {
                "key": s.key,
                "builder": s.builder,
                "params": dict(s.params),
                "exit_name": s.exit_name,
                "exit_params": dict(s.exit_params),
                "h": s.h,
                "block": LEAD_EVAL[s.key][1],
                "block_len": LEAD_EVAL[s.key][2],
            }
            for s in specs
        ],
        "k": K,
        "bonferroni_level": bonferroni_level(K),
        "btc_anchor_bars": len(btc),
        "btc_anchor_sha": _sha(btc),
        "windows": _window_bounds(args),
        "gate": (
            "per (lead x asset) cell: same-sign + practical + 2x/3x cost + one-sided "
            f"bootstrap p_le0 < {bonferroni_level(K)}; lane confirmed iff >=1 cell is a "
            "paper_candidate; BTC anchor reported not gated"
        ),
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    _, daily, is_member = _load(args)
    rows = []
    for symbol in ASSETS:
        candles = _fetch_asset(args, symbol)
        if len(candles) < MIN_BARS:
            rows.append({"asset": symbol, "feasible": False, "bars": len(candles)})
            continue
        train = split_60_20_20(candles)[0]
        feasible = universe_covers_train(daily, is_member, train)
        for spec in lead_specs():
            evaluator = LEAD_EVAL[spec.key][0]
            metrics = (
                evaluator(daily, train, spec, is_member=is_member)["metrics"]
                if feasible else None
            )
            rows.append({"asset": symbol, "lead": spec.key, "feasible": feasible,
                         "bars": len(candles), "metrics": metrics})
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _validate(args) -> int:
    btc, daily, is_member = _load(args)

    # BTC anchor x-check per lead (proves the breadth state + evaluator wiring).
    _, btc_val, btc_seal = split_60_20_20(btc)
    anchors = {}
    for spec in lead_specs():
        evaluator = LEAD_EVAL[spec.key][0]
        av = evaluator(daily, btc_val, spec, is_member=is_member)
        as_ = evaluator(daily, btc_seal, spec, is_member=is_member)
        anchors[spec.key] = {
            "ok": _anchor_ok(spec.key, av, as_),
            "validate_exp": av["metrics"]["expectancy_r"],
            "validate_n": av["metrics"]["trade_count"],
            "sealed_exp": as_["metrics"]["expectancy_r"],
            "sealed_n": as_["metrics"]["trade_count"],
        }
    anchor_ok = all(a["ok"] for a in anchors.values())

    rows: list[dict] = []
    for symbol in ASSETS:
        candles = _fetch_asset(args, symbol)
        if len(candles) < MIN_BARS:
            rows.append({"asset": symbol, "status": "infeasible", "bars": len(candles)})
            continue
        _, val, seal = split_60_20_20(candles)
        if not universe_covers_train(daily, is_member, val):
            rows.append({"asset": symbol, "status": "infeasible_universe"})
            continue
        for spec in lead_specs():
            evaluator, block, block_len = LEAD_EVAL[spec.key]
            v = evaluator(daily, val, spec, is_member=is_member)
            s = evaluator(daily, seal, spec, is_member=is_member)
            judge = judge_signal(
                v["metrics"], s["metrics"], v["records"] + s["records"], K,
                block=block, block_len=block_len,
            )
            status = "confirmed" if judge["verdict"] == "paper_candidate" else (
                "transfers_unconfirmed" if judge["verdict"] == "forward_candidate"
                else "negative")
            rows.append({
                "asset": symbol,
                "lead": spec.key,
                "status": status,
                "verdict": judge["verdict"],
                "validate_exp": v["metrics"]["expectancy_r"],
                "sealed_exp": s["metrics"]["expectancy_r"],
                "pooled": judge["pooled"],
                "boot_lo": judge["boot_lo"],
                "p_le_zero": judge["p_le_zero"],
                "same_sign": judge["same_sign"],
                "practical": judge["practical"],
                "cost": judge["cost"],
                "significant": judge["significant"],
            })

    verdict = "confirmed" if any(r.get("status") == "confirmed" for r in rows) \
        else "mechanism_unconfirmed"
    asof = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir)
    result_doc = {
        "lane": "breadth_xasset_confirm",
        "asof": asof,
        "assets": list(ASSETS),
        "timeframe": TF,
        "btc_anchor_sha": _sha(btc),
        "windows": _window_bounds(args),
        "bonferroni_alpha": bonferroni_level(K),
        "anchor_ok": anchor_ok,
        "anchors": anchors,
        "verdict": verdict,
        "rows": rows,
    }
    _write_json(out_dir / "RESULT.json", result_doc)

    lines = [
        "# Breadth-internal leads — cross-asset transfer confirmation (ETH/SOL)",
        "",
        f"## Verdict: {verdict.upper()}",
        "",
        f"- asof: {asof}",
        f"- bonferroni_alpha: {result_doc['bonferroni_alpha']}",
        f"- anchor_ok (BTC discovery reproduced): {anchor_ok}",
        "",
        "| asset | lead | status | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "lead" not in r:
            lines.append(f"| {r['asset']} | - | {r['status']} | - | - | - | - | - | - |")
            continue
        lines.append(
            f"| {r['asset']} | {r['lead']} | {r['status']} | {r['validate_exp']:.3f} | "
            f"{r['sealed_exp']:.3f} | {r['pooled']['trade_count']} | "
            f"{r['pooled']['expectancy_r']:.3f} | {r['boot_lo']:.3f} | {r['p_le_zero']:.4f} |"
        )
    lines.append(
        "\nPaper-only. Cross-asset transfer is an independent robustness axis "
        "(different traded leg, identical BTC-excluded breadth state). The BTC "
        f"discovery is anchor-x-checked (ok={anchor_ok}), never re-gated. "
        "mechanism_unconfirmed is the pre-committed expected outcome given both "
        "leads already failed the disjoint-universe cure.\n"
    )
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth-xasset-confirm")
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
