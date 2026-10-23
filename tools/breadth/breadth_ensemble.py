#!/usr/bin/env python3
"""Lane 3: diagnostic-only net-vote ensemble of survivors (paper-only)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import _load, _sha, split_60_20_20, universe_covers_train  # noqa: E402
from moonface.research.breadth_internal.ensemble import (  # noqa: E402
    evaluate_ensemble,
    load_survivors,
)
from moonface.kernel.power_harness import (  # noqa: E402
    bonferroni_level,
    bootstrap_expectancy,
    one_sided_lower,
    pooled_metrics,
)

SYMBOL = "BTCUSDT"
TF = "4h"
MIN_BARS = 300


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _members(args):
    survivors = load_survivors(args.result)
    keys = [s["spec"]["key"] for s in survivors]
    t0 = max((s["sealed_end"] for s in survivors), default=None)
    return survivors, keys, t0


def _forward_registration(survivors, keys, t0, out_dir: Path) -> None:
    lines = [
        "# Ensemble Forward Paper Registration (frozen, Lane 3)",
        "",
        "Net-vote ensemble of the forward-candidate survivors from Lanes 1-2.",
        "",
        "## Frozen members",
    ]
    for s in survivors:
        sp = s["spec"]
        lines.append(f"- `{sp['key']}` builder=`{sp['builder']}` params=`{sp['params']}`")
    lines += [
        "",
        "## Combination rule",
        "Daily net vote: each member emits +1/-1/0; ensemble state = sign(sum), "
        "ties -> FLAT. Mapped to BTC via non-overlapping transition entries "
        "(h=48), frozen atr_trail exit.",
        "",
        f"## t0 (forward start) = {t0}  (max member sealed-window end)",
        "",
        "## Resolution rule",
        "CONFIRM iff forward-only pooled n>=30 AND bootstrap CI lower bound > 0 "
        "AND forward-only exp > 0; REFUTE / early-kill at cumulative -30R.",
        "",
        "Paper-only. Diagnostic in-sample numbers are selection-biased and cannot "
        "promote anything; only this forward record carries weight.",
    ]
    (out_dir / "ENSEMBLE_FORWARD_REGISTRATION.md").write_text("\n".join(lines) + "\n")


def _register(args) -> int:
    survivors, keys, t0 = _members(args)
    out_dir = Path(args.out_dir)
    if len(survivors) < 2:
        _write_json(out_dir / "PREREGISTRATION.json", {
            "lane": "btc_breadth_ensemble", "status": "insufficient_members",
            "member_keys": keys, "asof": datetime.now(timezone.utc).isoformat()})
        return 0
    _write_json(out_dir / "PREREGISTRATION.json", {
        "lane": "btc_breadth_ensemble", "status": "registered",
        "asof": datetime.now(timezone.utc).isoformat(),
        "member_keys": keys, "t0": t0,
        "combination": "net_vote sign(sum), ties FLAT; entries_from_state h=48",
        "members": [s["spec"] for s in survivors],
    })
    _forward_registration(survivors, keys, t0, out_dir)
    return 0


def _diagnose(args) -> int:
    survivors, keys, t0 = _members(args)
    out_dir = Path(args.out_dir)
    if len(survivors) < 2:
        _write_json(out_dir / "RESULT.json",
                    {"lane": "btc_breadth_ensemble", "status": "insufficient_members",
                     "member_keys": keys})
        return 0
    btc, daily, is_member = _load(args)
    if len(btc) < MIN_BARS:
        print(f"FEASIBILITY FAIL: {len(btc)} BTC bars < {MIN_BARS}")
        return 2
    train, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        print("FEASIBILITY FAIL: universe daily history does not cover validate.")
        return 2

    specs = [s["spec"] for s in survivors]
    ens_val = evaluate_ensemble(daily, val, specs, is_member)
    ens_seal = evaluate_ensemble(daily, seal, specs, is_member)
    pooled = ens_val["records"] + ens_seal["records"]
    metrics = pooled_metrics(pooled)
    alpha = bonferroni_level(max(len(specs), 1))
    means, p_le0 = bootstrap_expectancy([r["net_r"] for r in pooled])
    boot_lo = one_sided_lower(means, alpha)

    asof = datetime.now(timezone.utc).isoformat()
    _write_json(out_dir / "RESULT.json", {
        "lane": "btc_breadth_ensemble", "status": "diagnostic_only",
        "asof": asof, "member_keys": keys, "t0": t0,
        "btc_sha": _sha(btc), "pooled": metrics,
        "boot_lo": boot_lo, "p_le_zero": p_le0,
        "caveat": "selection-biased (in-sample-of-components); cannot promote.",
    })
    lines = [
        "# BTC Breadth Ensemble (Lane 3) — DIAGNOSTIC ONLY",
        "",
        f"- asof: {asof}  members: {', '.join(keys)}  t0: {t0}",
        f"- pooled n: {metrics['trade_count']}  exp: {metrics['expectancy_r']:.3f}  "
        f"PF: {metrics['profit_factor']:.3f}  maxDD: {metrics['max_drawdown_r']:.2f}R",
        f"- boot_lo (alpha={alpha:.4f}): {boot_lo:.3f}  p_le0: {p_le0:.4f}",
        "",
        "**Selection-biased (in-sample-of-components): cannot promote anything.** "
        "The binding deliverable is `ENSEMBLE_FORWARD_REGISTRATION.md`.",
        "",
    ]
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))
    _forward_registration(survivors, keys, t0, out_dir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth-ensemble")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--diagnose", action="store_true")
    p.add_argument("--result", action="append", default=[], required=True,
                   help="path to a Lane 1/2 RESULT.json (repeatable)")
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
    if args.diagnose:
        return _diagnose(args)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
