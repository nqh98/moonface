# tools/engine/engine_calibration.py
"""Read-only score-calibration diagnostic for the frozen v2 engine.

Runs the calibration scoring pass + hypothetical-trade panels over historical
1h candles and emits the pre-registered report JSON (spec:
docs/research-log/specs/2026-07-04-v2-calibration-diagnostic-design.md;
frozen criteria: experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md).

DIAGNOSTIC ONLY — never gates, never mutates state, never recommends a
constant change. Touches no frozen value; the forward-paper clock is
unaffected.

Usage:
  .venv/bin/python -m tools.engine.engine_calibration \
      --start-ms 1577836800000 --end-ms 1782316800000 \
      --out experiments/engine/calibration_report_2026-07.json
"""
from __future__ import annotations

import argparse
import json

from moonface.data.bundle import load_bundle
from moonface.models.engine.calibration import build_report
from moonface.models.engine.config import load_engine_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-calibration")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000,
                   help="first scored bar has a full lookback window; 6000 "
                        "keeps the 1W macro gate live from bar one")
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms,
                         args.cache_dir)
    report = build_report(cfg, bundle.candles, args.warmup)
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
