# tools/engine/engine_audit.py
"""Read-only scoring component and weight audit CLI.

Runs either the price-only Stage 1 audit or the derivative-inclusive Stage 2
audit over historical 1h candles and emits the registered report JSON.

Spec: docs/research-log/specs/2026-07-05-scoring-audit-design.md

DIAGNOSTIC ONLY - never gates capital, never mutates state, never recommends a
constant change. Touches no frozen value; the v2.1 forward-paper clock is
unaffected.

Usage:
  .venv/bin/python -m tools.engine.engine_audit --stage 1 \
      --start-ms 1577836800000 --end-ms 1782316800000 \
      --out experiments/engine/audit_report_stage1.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json

from moonface.data.bundle import load_bundle
from moonface.models.engine.audit import build_audit_report
from moonface.models.engine.config import load_engine_config
from moonface.models.engine.deriv_history import build_deriv_by_index

COVERAGE_FLOOR = 0.90


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-audit")
    p.add_argument("--stage", type=int, choices=(1, 2), required=True)
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000,
                   help="first scored bar has a full lookback window")
    p.add_argument("--out", default=None)
    p.add_argument("--coverage-floor", type=float, default=COVERAGE_FLOOR,
                   help="Stage-2 deriv integrity gate")
    p.add_argument("--lookback-bars", type=int, default=None,
                   help="test-only window override; registered runs omit it")
    return p


def _archive_symbol(asset: dict) -> str:
    return asset["symbol"].split(":")[0].replace("/", "")


def _deriv_meta(archive_symbol: str, coverage, coverage_floor: float) -> dict:
    return {
        "archive_symbol": archive_symbol,
        "funding_coverage": round(coverage.funding_fraction(), 4),
        "oi_coverage": round(coverage.oi_fraction(), 4),
        "coverage_floor": coverage_floor,
    }


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    if args.lookback_bars is not None:
        cfg = dataclasses.replace(cfg, lookback_bars=args.lookback_bars)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms,
                         args.cache_dir)

    if len(bundle.candles) <= args.warmup:
        print(f"ERROR: {len(bundle.candles)} candles <= warmup "
              f"{args.warmup} - truncated data, refusing to run")
        return 2

    deriv_by_index = None
    deriv_meta = None
    if args.stage == 2:
        archive = _archive_symbol(cfg.asset)
        deriv_by_index, coverage = build_deriv_by_index(
            bundle.candles, args.warmup, archive, args.cache_dir)
        deriv_meta = _deriv_meta(archive, coverage, args.coverage_floor)
        if min(coverage.funding_fraction(),
               coverage.oi_fraction()) < args.coverage_floor:
            print(f"ERROR: deriv coverage below floor: {deriv_meta}")
            return 2

    report = build_audit_report(cfg, bundle.candles, args.warmup,
                                deriv_by_index=deriv_by_index,
                                stage=args.stage, deriv_meta=deriv_meta)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    print(text)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
