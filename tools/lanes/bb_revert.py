#!/usr/bin/env python3
"""Bollinger Band mean-reversion decomposition CLI (research-only).

Scores the bb_revert entry generator (LONG on a lower-band cross-down, SHORT on
an upper-band cross-up) over a small period x mult grid, exit-free, via the
shared score_variant path stats + bootstrap CI from tools.engine.smc_decompose, then
writes a JSON results doc + markdown report. No promotion, no edge claim."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent))                # import tools.engine.smc_decompose
sys.path.insert(0, str(_HERE.parent.parent / "src"))        # import moonface.*

from moonface.core.models import Candle  # noqa: E402,F401  (consistent w/ sibling tools)
from moonface.research.edge.signals import bb_revert  # noqa: E402
from tools.engine.smc_decompose import (  # noqa: E402,F401  (HORIZONS consumed via score_variant default)
    HORIZONS, _load_candles, score_variant, slice_events,
)


# period x mult sweep = 6 variants. Long & short both scored via the slices.
GRID: dict[str, tuple[list[dict], object]] = {
    "bb_revert": (
        [{"period": p, "mult": m} for p in (20, 50) for m in (2.0, 2.5, 3.0)],
        bb_revert,
    ),
}


def cmd_run(args) -> dict:
    candles = _load_candles(args)
    variants: dict[str, list[dict]] = {}
    for name, (param_grid, gen) in GRID.items():
        variants[name] = [score_variant(candles, gen, params)
                          for params in param_grid]
    doc = {
        "symbol": args.symbol, "tf": args.tf,
        "start_ms": args.start_ms, "end_ms": args.end_ms,
        "n_bars": len(candles), "variants": variants,
        "slices": {name: [{**{"params": r["params"]}, "slices": slice_events(r["events"])}
                          for r in rows]
                   for name, rows in variants.items()},
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"results_{args.tf}.json").write_text(json.dumps(doc, indent=2))
    return doc


def print_table(doc: dict) -> None:
    print(f"\n== {doc['symbol']} {doc['tf']}  bars={doc['n_bars']} ==")
    print(f"{'variant':<12}{'params':<28}{'h':<4}{'n':<6}{'win':<7}{'ret_r':<8}{'ci95'}")
    for name, rows in doc["variants"].items():
        for row in rows:
            p = json.dumps(row["params"], sort_keys=True)
            for h, b in row["horizons"].items():
                print(f"{name:<12}{p:<28}{h:<4}{b['n']:<6}{b['win_rate']:<7.2f}"
                      f"{b['mean_ret_r']:<8.3f}[{b['ci_lo']:.3f},{b['ci_hi']:.3f}]  ")


def render_report(docs: dict) -> str:
    """Markdown report from {out_dir: doc}. RESEARCH-ONLY banner; per-variant
    horizon table. No PASS/FAIL, no edge claim."""
    lines = [
        "# Bollinger Band mean-reversion decomposition — RESEARCH-ONLY", "",
        "> Diagnostic, not a strategy. No edge is claimed; the WAIT stance and",
        "> `experiments/PROGRAM_CONCLUSION.md` are unchanged. Exit-free forward-path",
        "> scoring (declumped events, 6/12/18/30-bar horizons) with a single-asset",
        "> bootstrap 95% CI on mean_ret_r — not a promotion gate.", "",
    ]
    for _out_dir, doc in docs.items():
        lines += [f"## {doc['symbol']} {doc['tf']}  (bars={doc['n_bars']})", "",
                  "| variant | params | h | n | win_rate | mean_ret_r | ci95 |",
                  "|---|---|---|---|---|---|---|"]
        for name, rows in doc["variants"].items():
            for row in rows:
                p = json.dumps(row["params"], sort_keys=True)
                for h, b in row["horizons"].items():
                    lines.append(
                        f"| {name} | {p} | {h} | {b['n']} | {b['win_rate']:.2f} "
                        f"| {b['mean_ret_r']:.3f} "
                        f"| [{b['ci_lo']:.3f}, {b['ci_hi']:.3f}] |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="BTC/USDT:USDT")
    p.add_argument("--tf", choices=["1h", "4h", "both"], default="4h")
    p.add_argument("--start-ms", type=int, default=1_577_836_800_000)  # 2020-01-01
    p.add_argument("--end-ms", type=int, default=2_000_000_000_000)    # all cached
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", default="experiments/bb_revert")
    p.add_argument("--from-1h", action="store_true", default=True,
                   help="derive 4h from the 1h cache (default on)")
    args = p.parse_args(argv)
    tfs = ["1h", "4h"] if args.tf == "both" else [args.tf]
    docs: dict[str, dict] = {}
    for tf in tfs:
        args.tf = tf
        doc = cmd_run(args)
        print_table(doc)
        docs[str(Path(args.out_dir) / f"results_{tf}.json")] = doc
    report = render_report(docs)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.out_dir) / "REPORT.md").write_text(report)


if __name__ == "__main__":
    main()
