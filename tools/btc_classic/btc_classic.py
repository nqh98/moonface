#!/usr/bin/env python3
"""Staged from-scratch BTC classical-strategy CLI (paper-only).

Re-judges a frozen K=6 family of classical BTC directional strategies on fresh
OOS evidence via the power-honest harness (bootstrap CI + Bonferroni). Inherits
no prior verdict. Paper-only; no live capital.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import _sha  # noqa: E402
from moonface.data.series import align_funding  # noqa: E402
from moonface.research.btc_classic.evaluate import evaluate_spec  # noqa: E402
from moonface.research.btc_classic.grid import all_specs  # noqa: E402
from moonface.kernel.power_harness import bonferroni_level, judge_signal  # noqa: E402
from moonface.research.universe_data import (  # noqa: E402
    fetch_funding_rates,
    fetch_perp_candles,
)

SYMBOL = "BTCUSDT"
TF = "4h"
BAR_MS = 14_400_000  # 4h
MIN_BARS = 300


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _load(args):
    btc = fetch_perp_candles(SYMBOL, TF, args.start_ms, args.end_ms, args.cache_dir)
    points = fetch_funding_rates(SYMBOL, args.start_ms, args.end_ms, args.cache_dir)
    funding = align_funding(btc, points)
    return btc, funding


def _split_parallel(btc, funding):
    n = len(btc)
    a, b = int(0.6 * n), int(0.8 * n)
    return (
        (btc[:a], funding[:a]),
        (btc[a:b], funding[a:b]),
        (btc[b:], funding[b:]),
    )


def _covers_window(btc, args) -> bool:
    if len(btc) < MIN_BARS:
        return False
    return (
        btc[0].timestamp_ms <= args.start_ms + 2 * BAR_MS
        and btc[-1].timestamp_ms >= args.end_ms - 2 * BAR_MS
    )


def _window_bounds(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    t_end = args.start_ms + int(span * 0.6)
    v_end = args.start_ms + int(span * 0.8)
    return {
        "train": [args.start_ms, t_end],
        "validate": [t_end, v_end],
        "sealed": [v_end, args.end_ms],
    }


def _spec_doc(spec) -> dict:
    return {
        "key": spec.key,
        "kind": spec.kind,
        "builder": spec.builder,
        "params": dict(spec.params),
        "exit_name": spec.exit_name,
        "exit_params": dict(spec.exit_params),
    }


_GATE_TEXT = (
    "OOS pooled-bootstrap one-sided lower bound > 0 at alpha/K = 0.05/6 "
    "(~0.00833), plus same-sign across validate+sealed, practical "
    "(PF>=1.15, exp>0, |maxDD|<=30R), and 2x/3x cost. forward_candidate if "
    "OOS-positive in sign but not significant; else negative."
)


def _feasible_or_msg(btc, args) -> str | None:
    if not _covers_window(btc, args):
        return (
            f"FEASIBILITY FAIL: {len(btc)} BTC bars and/or window coverage "
            f"[{btc[0].timestamp_ms if btc else 'NA'}.."
            f"{btc[-1].timestamp_ms if btc else 'NA'}] does not span the frozen "
            f"[{args.start_ms}..{args.end_ms}] (stale/short cache?). Refetch BTC "
            "4h candles for the full window before running."
        )
    return None


def _register(args) -> int:
    btc, _ = _load(args)
    msg = _feasible_or_msg(btc, args)
    if msg:
        print(msg)
        return 2
    specs = all_specs()
    prereg = {
        "lane": "btc_classic_from_scratch",
        "lane_description": (
            "Frozen K=6 classical BTC directional family, judged from scratch on "
            "fresh OOS evidence by the power-honest harness. Inherits no prior "
            "verdict."
        ),
        "asof": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "timeframe": TF,
        "k_signals": len(specs),
        "bonferroni_level": bonferroni_level(len(specs)),
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": _window_bounds(args),
        "gate": _GATE_TEXT,
        "specs": [_spec_doc(s) for s in specs],
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    btc, funding = _load(args)
    msg = _feasible_or_msg(btc, args)
    if msg:
        print(msg)
        return 2
    (tr_c, tr_f), _, _ = _split_parallel(btc, funding)
    rows = []
    for spec in all_specs():
        out = evaluate_spec(tr_c, tr_f, spec)
        rows.append({"key": spec.key, "metrics": out["metrics"]})
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _forward_doc(row: dict, out_dir: Path) -> None:
    spec = row["spec"]
    lines = [
        f"# {spec['key'].upper()} Forward Paper Registration (frozen)",
        "",
        "Pre-registers the forward paper continuation for a frozen classical BTC "
        "spec that met the forward-candidate verdict on the unopened holdout.",
        "",
        "## Frozen spec",
        f"- key: `{spec['key']}`",
        f"- kind/builder: `{spec['kind']}` / `{spec['builder']}`",
        f"- params: `{spec['params']}`",
        f"- exit: `{spec['exit_name']}` `{spec['exit_params']}`",
        "",
        "## Validation result (unopened holdout)",
        f"- verdict: `{row['verdict']}`",
        f"- validate exp: `{row['validate']['metrics']['expectancy_r']}`",
        f"- sealed exp: `{row['sealed']['metrics']['expectancy_r']}`",
        f"- pooled exp: `{row['pooled']['expectancy_r']}` (n={row['pooled']['trade_count']})",
        f"- boot_lo: `{row['boot_lo']}`  p_le0: `{row['p_le_zero']}`",
        "",
        "## Resolution rule (frozen)",
        "CONFIRM iff forward-only pooled n >= 30 AND bootstrap lower bound > 0 AND "
        "forward-only expectancy > 0. REFUTE / early-kill on cumulative -30R.",
        "",
        "## Honest caveat",
        "Paper-only. Forward registration does not authorize live capital or modify "
        "any frozen registry.",
    ]
    (out_dir / f"{spec['key'].upper()}_FORWARD_REGISTRATION.md").write_text(
        "\n".join(lines) + "\n"
    )


def _validate(args) -> int:
    btc, funding = _load(args)
    msg = _feasible_or_msg(btc, args)
    if msg:
        print(msg)
        return 2
    _, (va_c, va_f), (se_c, se_f) = _split_parallel(btc, funding)
    specs = all_specs()
    rows: list[dict] = []
    for spec in specs:
        validate = evaluate_spec(va_c, va_f, spec)
        sealed = evaluate_spec(se_c, se_f, spec)
        judge = judge_signal(
            validate["metrics"],
            sealed["metrics"],
            validate["records"] + sealed["records"],
            len(specs),
        )
        rows.append({
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
        })

    if any(r["verdict"] == "paper_candidate" for r in rows):
        verdict = "paper_candidate"
    elif any(r["verdict"] == "forward_candidate" for r in rows):
        verdict = "forward_candidate"
    else:
        verdict = "negative"

    asof = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir)
    _write_json(out_dir / "RESULT.json", {
        "lane": "btc_classic_from_scratch",
        "asof": asof,
        "symbol": SYMBOL,
        "timeframe": TF,
        "btc_bars": len(btc),
        "btc_sha": _sha(btc),
        "windows": _window_bounds(args),
        "bonferroni_alpha": bonferroni_level(len(specs)),
        "verdict": verdict,
        "rows": rows,
    })

    lines = [
        "# BTC Classic (from-scratch re-analysis)",
        "",
        f"## Verdict: {verdict.upper() if verdict != 'negative' else 'NEGATIVE'}",
        "",
        f"- asof: {asof}",
        f"- data_sha: {_sha(btc)}",
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
            f"{r['boot_lo']:.3f} | {r['p_le_zero']:.4f} | {r['verdict']} |"
        )
    lines.append(
        "\nPaper-only, BTC futures only. forward_candidate at n<30 is the expected "
        "underpowered outcome, not a failure.\n"
    )
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))

    for r in rows:
        if r["verdict"] == "forward_candidate":
            _forward_doc(r, out_dir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="btc-classic")
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
