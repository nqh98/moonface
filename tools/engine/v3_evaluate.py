"""Pre-registered, read-only backtest evaluation of the v3 engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from moonface.data.bundle import load_bundle
from moonface.models.engine.config import load_engine_config
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import ASSETS, build_eval_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="v3-evaluate")
    p.add_argument("--v22-engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=6000)
    p.add_argument("--lookback", type=int, default=400)
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None, loaders: dict | None = None) -> int:
    args = build_parser().parse_args(argv)
    load = loaders or {k: load_bundle for k in ASSETS}
    cfg_v22 = load_engine_config(args.v22_engine)
    cfg_v3 = EngineConfigV3()

    def candles(key: str):
        return load[key](ASSETS[key], args.start_ms, args.end_ms,
                         args.cache_dir).candles

    report = build_eval_report(
        candles("BTC"),
        candles("ETH"),
        candles("SOL"),
        cfg_v3,
        cfg_v22,
        args.warmup,
        args.lookback,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
