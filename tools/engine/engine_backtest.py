# tools/engine/engine_backtest.py
"""Replay the stateful confluence engine over historical 1h candles through the
SAME evaluate_engine path used live, so the backtest and the forward run are
faithful by construction. Prints the forward scorecard. NOT a DSR/pass gate —
a sanity check and a way to set sane defaults (forward-discipline bar)."""
from __future__ import annotations

import argparse
import json

from moonface.core.bundle import DataBundle
from moonface.data.bundle import load_bundle
from moonface.models.engine.config import (EngineConfig, engine_hash,
                                           load_engine_config)
from moonface.models.engine.engine import evaluate_engine
from moonface.models.engine.scorecard import engine_scorecard


def replay(cfg: EngineConfig, candles: list, warmup: int) -> list[dict]:
    """Incrementally evaluate the engine bar-by-bar, accumulating synthetic
    journal entries with the exact schema _emit_engine writes.

    Live faithfulness: each tick the live loop fetches and feeds exactly
    cfg.lookback_bars candles (cli.py: start_ms = end_ms - lookback*tf_ms), so
    the replay feeds the SAME rolling lookback_bars window — never the full
    expanding history. Feeding the whole history overstates, because the
    expanding vol_ratio baseline live never has lifts the score (see
    experiments/engine/FORWARD_FAITHFUL_BACKTEST_2026-06-24.md)."""
    version = engine_hash(cfg)
    window = cfg.lookback_bars
    entries: list[dict] = []
    for j in range(warmup, len(candles)):
        lo = max(0, j + 1 - window)
        sub = DataBundle(candles=candles[lo:j + 1])
        last = candles[j]
        res = evaluate_engine(cfg, sub, entries, now_ms=last.timestamp_ms)
        sig = res.signal
        entries.append({
            "ts_ms": last.timestamp_ms,
            "candle_ts_ms": last.timestamp_ms,
            "decision": sig.decision,
            "price": sig.price,
            "invalidation": sig.invalidation,
            "fraction": sig.fraction,
            "status": "engine",
            "style": "backtest",
            "strategy_version": version,
            "confidence": sig.confidence,
            "action": res.action,
            "entry_price": res.entry_price,
            "stop": res.stop,
            "extreme": res.extreme,
            "atr_at_entry": res.atr_at_entry,
            "atr_frac": res.atr_frac,
            "bars_held": res.bars_held,
            "realized_r": res.realized_r,
            "regime_trend": res.regime_trend,
            "regime_vol": res.regime_vol,
            "reason": sig.reason,
        })
    return entries


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-backtest")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=400)
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms, args.cache_dir)
    entries = replay(cfg, bundle.candles, args.warmup)
    sc = engine_scorecard(entries, cfg)
    print(json.dumps(sc, indent=2, sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
