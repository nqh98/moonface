"""Read-only ablation report for the confluence engine."""
from __future__ import annotations

import argparse
import json
import time

from moonface.data.bundle import load_bundle
from moonface.data.ohlcv import TIMEFRAME_MS
from moonface.models.engine.ablation import gate_ablation
from moonface.models.engine.config import engine_hash, load_engine_config
from moonface.models.engine.discipline import engine_entries
from moonface.models.journal import read_entries

WARMUP_BARS = 60


def _now_ms() -> int:
    return int(time.time() * 1000)


def _rounded_end_ms(now_ms: int, timeframe_ms: int) -> int:
    return now_ms - (now_ms % timeframe_ms)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-ablation")
    p.add_argument("--journal", default="journal/signals.jsonl")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--cache-dir", default=".backtest_cache")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    entries = read_entries(args.journal)
    version = engine_hash(cfg)
    mine = engine_entries(entries, version)
    veto_ts: list[int] = []
    for entry in mine:
        if not entry.get("veto"):
            continue
        ts_ms = entry.get("candle_ts_ms")
        if ts_ms is None:
            continue
        try:
            veto_ts.append(int(ts_ms))
        except (TypeError, ValueError):
            continue

    if not veto_ts:
        print(json.dumps(gate_ablation(entries, [], cfg), indent=2, sort_keys=True))
        return 0

    timeframe_ms = TIMEFRAME_MS[cfg.asset["timeframe"]]
    start_ms = min(veto_ts) - WARMUP_BARS * timeframe_ms
    end_ms = _rounded_end_ms(_now_ms(), timeframe_ms)
    bundle = load_bundle(cfg.asset, start_ms, end_ms, args.cache_dir)
    report = gate_ablation(entries, bundle.candles, cfg)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
