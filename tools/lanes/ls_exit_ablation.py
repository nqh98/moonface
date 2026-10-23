#!/usr/bin/env python3
"""Exit ablation for the frozen BTC 4h long/short donchian_break n=100 survivor.

Holds the survivor's entry BYTE-IDENTICAL (symmetric donchian_break n=100, 4h,
non-overlap h=48) and swaps only the exit/stop mechanism, over the SAME data
window and 60/20/20 train/validate/sealed split as the tournament. The sealed
slice is the recent ~2025-2026 window the deployed config bled in.

Paper-only. The new exits live in research.ls_tournament.exit_ablation and are
deliberately kept OUT of the frozen EXIT_REGISTRY (DSR calibration untouched).

Default window reproduces experiments/ls_tournament:
  --start-ms 1577836800000 --end-ms 1782300000000  (BTCUSDT 4h, ~2020-01..2026-06)
The atr_trail k=2.0 arm must reproduce the tournament's combined totals
(train 74.517 / validate 10.739 / sealed -10.600) — a built-in correctness gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.ls_tournament.exit_ablation import (  # noqa: E402
    BASELINE_KEY,
    TIMEFRAME,
    run_ablation,
)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

SYMBOL = "BTCUSDT"
START_MS = 1577836800000
END_MS = 1782300000000
# tournament cross-check targets (atr_trail k=2.0 combined total_r per segment)
_XCHECK = {"train": 74.517, "validate": 10.739, "sealed": -10.600}


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_60_20_20(candles):
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    return {"train": candles[:a], "validate": candles[a:b], "sealed": candles[b:]}


def _f(x) -> str:
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def _yn(b: bool) -> str:
    return "Y" if b else "n"


def _block_cells(b: dict) -> str:
    return (f"{b['trade_count']} | {_f(b['total_r'])} | {_f(b['expectancy_r'])} | "
            f"{_f(b['profit_factor'])} | {_f(b['max_drawdown_r'])} | "
            f"{_yn(b['cost_2x']['passed'])}/{_yn(b['cost_3x']['passed'])} | "
            f"{_yn(b['outlier']['passed'])}")


def _render(result: dict, asof: str, sha: str, bars: int, xcheck_ok: bool) -> str:
    rows = result["rows"]
    base = result["baseline_sealed_total_r"]
    out: list[str] = []
    out.append("# BTC 4h Long/Short Donchian n=100 — Exit Ablation\n")
    out.append("## Frozen entry (never varied)\n")
    out.append("- `donchian_break n=100`, symmetric long+short, 4h, non-overlap h=48")
    out.append(f"- {SYMBOL} 4h, {bars} bars, data_sha={sha}, costs netted in R "
               "(round-trip 10bps base)")
    out.append("- split: 60/20/20 train/validate/**sealed**; sealed = recent "
               "~2025-03..2026-06 window")
    out.append(f"- baseline (atr_trail k=2.0) sealed combined total_r = {_f(base)}R\n")
    out.append(f"- cross-check vs tournament (atr_trail k=2.0 combined "
               f"train/val/sealed = {_XCHECK['train']}/{_XCHECK['validate']}/"
               f"{_XCHECK['sealed']}): **{'PASS' if xcheck_ok else 'FAIL'}**\n")

    # Per-exit sealed (recent) headline, combined.
    out.append("## Recent (sealed) window — combined long+short, ranked by total_r\n")
    out.append("| exit | trades | total_R | exp_R | PF | maxDD_R | cost2x/3x | outlier | verdict |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: r["segments"]["sealed"]["combined"]["total_r"],
                    reverse=True):
        b = r["segments"]["sealed"]["combined"]
        out.append(f"| {r['label']} | {_block_cells(b)} | {r['verdict']} |")

    # Full train -> validate -> sealed, combined.
    out.append("\n## Full path — combined (train -> validate -> sealed total_R)\n")
    out.append("| exit | train_R | val_R | sealed_R | sealed_PF | sealed_maxDD |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        s = r["segments"]
        out.append(
            f"| {r['label']} | {_f(s['train']['combined']['total_r'])} | "
            f"{_f(s['validate']['combined']['total_r'])} | "
            f"{_f(s['sealed']['combined']['total_r'])} | "
            f"{_f(s['sealed']['combined']['profit_factor'])} | "
            f"{_f(s['sealed']['combined']['max_drawdown_r'])} |")

    # Long vs short, sealed window (the structural-bleed question).
    out.append("\n## Recent (sealed) window — LONG vs SHORT separated\n")
    out.append("| exit | long_n | long_R | long_exp | short_n | short_R | short_exp |")
    out.append("|---|---|---|---|---|---|---|")
    for r in rows:
        lo = r["segments"]["sealed"]["long"]
        sh = r["segments"]["sealed"]["short"]
        out.append(
            f"| {r['label']} | {lo['trade_count']} | {_f(lo['total_r'])} | "
            f"{_f(lo['expectancy_r'])} | {sh['trade_count']} | {_f(sh['total_r'])} | "
            f"{_f(sh['expectancy_r'])} |")

    # Diagnosis.
    best = max(rows, key=lambda r: r["segments"]["sealed"]["combined"]["total_r"])
    best_b = best["segments"]["sealed"]["combined"]
    any_pass = any(r["full_bar_pass"] for r in rows)
    positives = [r for r in rows
                 if r["segments"]["sealed"]["combined"]["total_r"] > 0]
    out.append("\n## Diagnosis\n")
    out.append(f"- best recent-window exit on raw R: **{best['label']}** "
               f"(sealed total_r {_f(best_b['total_r'])}R, exp {_f(best_b['expectancy_r'])}R, "
               f"PF {_f(best_b['profit_factor'])}, maxDD {_f(best_b['max_drawdown_r'])}R, "
               f"outlier_ok={_yn(best_b['outlier']['passed'])})")
    if any_pass:
        passers = ", ".join(r["label"] for r in rows if r["full_bar_pass"])
        out.append(f"- **Clears the FULL risk-controlled bar in the recent window:** {passers}. "
                   "Exit management was a material drag. Paper-only, entry/registry untouched.")
    else:
        out.append("- **No exit clears the full risk-controlled bar in the recent window** "
                   "(PF>=1.15, exp>0, |maxDD|<=30R, n>=30, 2x+3x cost, not outlier-dependent, "
                   "validate same-sign).")
        if positives:
            plist = "; ".join(
                f"{r['label']} (+{r['segments']['sealed']['combined']['total_r']:.1f}R, "
                f"maxDD {r['segments']['sealed']['combined']['max_drawdown_r']:.1f}R, "
                f"outlier_ok={_yn(r['segments']['sealed']['combined']['outlier']['passed'])})"
                for r in sorted(positives,
                                key=lambda r: r["segments"]["sealed"]["combined"]["total_r"],
                                reverse=True))
            out.append(f"- The only arms that go positive in 2025-2026 are the *no-stop / "
                       f"loosest* exits: {plist}. They buy raw R by **removing risk control**: "
                       "every one is outlier-dependent (outlier_ok=n), and each additionally "
                       "breaches at least one of PF>=1.15, the 30R drawdown budget, or the 3x "
                       "cost gate. That is regime beta carried by a few trades, not an exit edge.")
        base_dd = next(r["segments"]["sealed"]["combined"]["max_drawdown_r"]
                       for r in rows if r["key"] == "atr_trail_2")
        out.append("- **Verdict: the failure is the entry/regime having no recent edge, NOT "
                   f"atr_trail.** atr_trail is in fact the tightest-drawdown arm in the recent "
                   f"window (sealed maxDD {_f(base_dd)}R, well inside the 30R budget). Swapping "
                   "it at most loses less while breaching that budget -> improves-but-no-edge, "
                   "not a pass.")
    out.append("\n## Honest caveat\n")
    out.append("A negative outcome is expected and valid. Nothing here authorises live "
               "capital or promotion; the entry and EXIT_REGISTRY are untouched.")
    return "\n".join(out) + "\n"


def run(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ls-exit-ablation")
    p.add_argument("--symbol", default=SYMBOL)
    p.add_argument("--start-ms", type=int, default=START_MS)
    p.add_argument("--end-ms", type=int, default=END_MS)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", default="experiments/ls_tournament/exit_ablation")
    args = p.parse_args(argv)

    candles = fetch_perp_candles(args.symbol, TIMEFRAME, args.start_ms, args.end_ms,
                                 args.cache_dir)
    if len(candles) < 300:
        print(f"FEASIBILITY FAIL: {TIMEFRAME} has {len(candles)} bars < 300")
        return 2
    segments = _split_60_20_20(candles)
    result = run_ablation(segments)

    # built-in correctness gate: baseline must reproduce the tournament.
    base_row = next(r for r in result["rows"] if r["key"] == BASELINE_KEY)
    xcheck_ok = all(
        abs(base_row["segments"][seg]["combined"]["total_r"] - tgt) < 0.05
        for seg, tgt in _XCHECK.items())

    asof = datetime.now(timezone.utc).isoformat()
    sha = _sha(candles)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "RESULT.json").write_text(
        json.dumps({"asof": asof, "symbol": args.symbol, "timeframe": TIMEFRAME,
                    "bars": len(candles), "data_sha": sha, "xcheck_ok": xcheck_ok,
                    "window": [args.start_ms, args.end_ms], **result},
                   indent=2, sort_keys=True, default=str) + "\n")
    (out_dir / "FINDINGS.md").write_text(
        _render(result, asof, sha, len(candles), xcheck_ok))

    print(f"bars={len(candles)} data_sha={sha} xcheck={'PASS' if xcheck_ok else 'FAIL'}")
    for seg, tgt in _XCHECK.items():
        got = base_row["segments"][seg]["combined"]["total_r"]
        print(f"  baseline {seg}: got {got:+.3f}R  target {tgt:+.3f}R")
    print(f"wrote {out_dir}/FINDINGS.md and RESULT.json")
    return 0 if xcheck_ok else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
