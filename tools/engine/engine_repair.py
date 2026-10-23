"""Pre-registered trend-score repair evaluation CLI.

Runs the single registered evaluation of the three audit-licensed trend-book
scoring repairs and emits the registered report JSON.

Spec: docs/research-log/specs/2026-07-05-trend-score-repair-design.md
Pre-reg: experiments/engine/TREND_SCORE_REPAIR_2026-07.md

DIAGNOSTIC ONLY - never gates capital, never mutates state, never changes a
frozen constant. The v2.2 forward-paper clock is unaffected; any v2.3 is a
separate human-gated registration.

Registered usage:
  .venv/bin/python -m tools.engine.engine_repair \
      --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
      --out experiments/engine/repair_report_2026-07.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json

from moonface.data.bundle import load_bundle
from moonface.models.engine.config import load_engine_config
from moonface.models.engine.repair import (
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    build_repair_report,
)

YEAR_MS = 365 * 24 * 3_600_000


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-repair")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000,
                   help="first scored bar has a full lookback window")
    p.add_argument("--out", default=None)
    p.add_argument("--lookback-bars", type=int, default=None,
                   help="test-only window override; registered runs omit it")
    p.add_argument("--train-end-ms", type=int, default=TRAIN_END_TS_MS,
                   help="test-only boundary override; registered runs omit it")
    p.add_argument("--sealed-start-ms", type=int,
                   default=SEALED_START_TS_MS,
                   help="test-only boundary override; registered runs omit it")
    return p


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

    if (args.sealed_start_ms == SEALED_START_TS_MS
            and bundle.candles[-1].timestamp_ms
            < SEALED_START_TS_MS + YEAR_MS):
        print("ERROR: sealed segment shorter than 12 months - "
              "refusing to run (spec section 2)")
        return 2

    report = build_repair_report(cfg, bundle.candles, args.warmup,
                                 train_end_ts_ms=args.train_end_ms,
                                 sealed_start_ts_ms=args.sealed_start_ms)
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
