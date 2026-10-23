#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.data.ohlcv import OhlcvCache, fetch_history
from moonface.research.edge.exit_score import ENTRY_SPECS_BY_TF, run_exit_battery
from moonface.core.exits import EXIT_REGISTRY
from moonface.core.models import Candle


def _render_markdown(rows: list, timeframe: str = "1h") -> str:
    lines = [
        "# MoonFace Exit-Probe Leaderboard",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframe: {timeframe}",
        f"- rows scored: {len(rows)}",
        "",
        "| entry | exit | exit params | rsch exp | rsch n | rsch maxDD | "
        "OOS exp | OOS net R | OOS n | valid |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.entry} | {r.exit} | {r.exit_params} | "
            f"{r.research_expectancy_r} | {r.research_trades} | {r.research_max_dd_r} | "
            f"{r.oos_expectancy_r} | {r.oos_net_r} | {r.oos_trades} | {r.valid} |")
    return "\n".join(lines) + "\n"


def run_exit_probe(exchange: str, symbol: str, start_ms: int, end_ms: int,
                   cache_dir: str, oos_tail_bars: int, warmup: int, future_bars: int,
                   out_root: Path, timeframe: str = "1h") -> Path:
    cache = OhlcvCache(cache_dir)
    candles: list[Candle] = fetch_history(exchange, symbol, timeframe,
                                          start_ms, end_ms, cache)
    try:
        entry_specs = ENTRY_SPECS_BY_TF[timeframe]
    except KeyError:
        raise SystemExit(
            f"no entry set defined for timeframe {timeframe!r}; "
            f"known: {sorted(ENTRY_SPECS_BY_TF)}")
    rows = run_exit_battery(candles, entry_specs, EXIT_REGISTRY,
                            oos_tail_bars=oos_tail_bars, warmup=warmup,
                            future_bars=future_bars)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leaderboard.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2, sort_keys=True),
        encoding="utf-8")
    (out_dir / "leaderboard.md").write_text(
        _render_markdown(rows, timeframe), encoding="utf-8")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="MoonFace exit probe.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT:USDT")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--oos-tail-bars", type=int, default=4380)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--future-bars", type=int, default=48)
    parser.add_argument("--out-root", default="experiments/exits")
    parser.add_argument("--timeframe", default="1h")
    args = parser.parse_args()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(args.years * 365 * 86_400_000)
    out_dir = run_exit_probe(
        exchange=args.exchange, symbol=args.symbol, start_ms=start_ms, end_ms=now_ms,
        cache_dir=args.cache_dir, oos_tail_bars=args.oos_tail_bars,
        warmup=args.warmup, future_bars=args.future_bars,
        out_root=Path(args.out_root), timeframe=args.timeframe)
    print(f"Leaderboard written to {out_dir}")


if __name__ == "__main__":
    main()