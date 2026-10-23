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
from moonface.research.edge.score import run_probe_battery
from moonface.research.edge.signals import REGISTRY
from moonface.config import Settings
from moonface.core.models import Candle


def _render_markdown(rows: list, timeframe: str = "1h") -> str:
    lines = [
        "# MoonFace Edge-Discovery Leaderboard",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframe: {timeframe}",
        f"- signals scored: {len(rows)}",
        "",
        "| signal | params | brkt trades | brkt net R | brkt exp | brkt win | "
        "valid | OOS net R | OOS n | hzn exp | hzn win | hzn OOS exp | hzn OOS n |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.signal} | {r.params} | {r.bracket_trades} | {r.bracket_net_r} | "
            f"{r.bracket_expectancy_r} | {r.bracket_win_rate} | {r.bracket_valid} | "
            f"{r.bracket_oos_net_r} | {r.bracket_oos_trades} | "
            f"{r.horizon_expectancy_r} | {r.horizon_win_rate} | "
            f"{r.horizon_oos_expectancy_r} | {r.horizon_oos_trades} |")
    return "\n".join(lines) + "\n"


def run_probe(
    exchange: str,
    symbol: str,
    start_ms: int,
    end_ms: int,
    cache_dir: str,
    settings: Settings,
    fee_rate: float,
    slippage: float,
    k: float,
    m: float,
    n_bars: int,
    atr_period: int,
    oos_tail_bars: int,
    warmup: int,
    future_bars: int,
    out_root: Path,
    timeframe: str = "1h",
) -> Path:
    cache = OhlcvCache(cache_dir)
    candles: list[Candle] = fetch_history(exchange, symbol, timeframe,
                                          start_ms, end_ms, cache)
    rows = run_probe_battery(
        candles, REGISTRY, k=k, m=m, n_bars=n_bars, atr_period=atr_period,
        fee_rate=fee_rate, slippage=slippage, oos_tail_bars=oos_tail_bars,
        warmup=warmup, future_bars=future_bars,
    )
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
    parser = argparse.ArgumentParser(description="MoonFace edge-discovery probe.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT:USDT")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--k", type=float, default=1.0)
    parser.add_argument("--m", type=float, default=2.0)
    parser.add_argument("--n-bars", type=int, default=24)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--oos-tail-bars", type=int, default=4380)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--future-bars", type=int, default=48)
    parser.add_argument("--out-root", default="experiments/edge")
    parser.add_argument("--timeframe", default="1h")
    args = parser.parse_args()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(args.years * 365 * 86_400_000)
    out_dir = run_probe(
        exchange=args.exchange, symbol=args.symbol, start_ms=start_ms, end_ms=now_ms,
        cache_dir=args.cache_dir, settings=Settings.from_env(),
        fee_rate=args.fee_rate, slippage=args.slippage, k=args.k, m=args.m,
        n_bars=args.n_bars, atr_period=args.atr_period,
        oos_tail_bars=args.oos_tail_bars, warmup=args.warmup,
        future_bars=args.future_bars, out_root=Path(args.out_root),
        timeframe=args.timeframe,
    )
    print(f"Leaderboard written to {out_dir}")


if __name__ == "__main__":
    main()
