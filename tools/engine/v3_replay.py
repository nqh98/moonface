# tools/engine/v3_replay.py
"""Diagnostic replay of the v3 regime-mechanism engine over historical candles.

PLUMBING VALIDATION ONLY — reports how the regime matrix routes and how often
each specialist fires. It computes NO returns and is NOT an edge test or a
verdict; it exists to confirm the engine is alive and routing sanely before any
statistical evaluation is designed. Running it does not touch or contaminate
any future holdout (no forward returns are observed).

Usage:
  .venv/bin/python -m tools.engine.v3_replay \
      --start-ms 1577836800000 --end-ms 1782316800000 \
      --out experiments/engine/v3_replay_2026-07.json
"""
from __future__ import annotations

import argparse
import json

from moonface.data.bundle import load_bundle
from moonface.models.engine.v3.config_v3 import (
    EngineConfigV3,
    load_engine_config_v3,
)
from moonface.models.engine.v3.replay import replay_distribution


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="v3-replay")
    p.add_argument("--engine", default=None,
                   help="optional EngineConfigV3 JSON; omitted -> frozen defaults")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--lookback", type=int, default=400,
                   help="bounded trailing window per bar (>= largest indicator "
                        "lookback); keeps a multi-year run linear")
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = (load_engine_config_v3(args.engine) if args.engine
           else EngineConfigV3())
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms, args.cache_dir)
    report = replay_distribution(bundle.candles, cfg, lookback=args.lookback)
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
