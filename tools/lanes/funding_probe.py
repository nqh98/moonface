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
from moonface.data.series import (
    FundingCache, align_funding, fetch_funding_history)
from moonface.research.edge.funding_signals import (
    make_funding_confirm, make_funding_fade, make_funding_flip)
from moonface.research.edge.score import run_probe_battery
from moonface.core.models import Candle

_DAY_MS = 86_400_000

# Small, pre-committed grids (bars). See the design doc's multiple-comparisons note.
FADE_GRID = [{"window": 60, "z_thr": 1.5}, {"window": 60, "z_thr": 2.0},
             {"window": 180, "z_thr": 1.5}, {"window": 180, "z_thr": 2.0}]
CONFIRM_GRID = [{"persist": 6, "lvl": 0.0001}, {"persist": 6, "lvl": 0.0003},
                {"persist": 12, "lvl": 0.0001}, {"persist": 12, "lvl": 0.0003}]
FLIP_GRID = [{"debounce": 6}]


def build_registry(funding: list[float | None]) -> dict:
    """Runtime registry: closures bind the aligned funding array; grids are static."""
    return {
        "funding_fade": (make_funding_fade(funding), FADE_GRID),
        "funding_confirm": (make_funding_confirm(funding), CONFIRM_GRID),
        "funding_flip": (make_funding_flip(funding), FLIP_GRID),
    }


def render_markdown(rows: list, timeframe: str, funding_symbol: str) -> str:
    lines = [
        "# MoonFace Funding-Rate Edge Probe",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframe: {timeframe}",
        f"- funding symbol: {funding_symbol}",
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


def write_report(
    out_dir: Path, rows: list, timeframe: str, funding_symbol: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "funding_probe.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2, sort_keys=True),
        encoding="utf-8")
    (out_dir / "funding_probe.md").write_text(
        render_markdown(rows, timeframe, funding_symbol), encoding="utf-8")
    return out_dir


def run_funding_probe(
    exchange: str, symbol: str, funding_symbol: str, start_ms: int, end_ms: int,
    cache_dir: str, timeframe: str, k: float, m: float, n_bars: int, atr_period: int,
    fee_rate: float, slippage: float, oos_tail_bars: int, warmup: int, future_bars: int,
    out_root: Path,
) -> Path:
    candles: list[Candle] = fetch_history(
        exchange, symbol, timeframe, start_ms, end_ms, OhlcvCache(cache_dir))
    points = fetch_funding_history(
        exchange, funding_symbol, start_ms, end_ms, FundingCache(cache_dir))
    funding = align_funding(candles, points)
    rows = run_probe_battery(
        candles, build_registry(funding), k=k, m=m, n_bars=n_bars,
        atr_period=atr_period, fee_rate=fee_rate, slippage=slippage,
        oos_tail_bars=oos_tail_bars, warmup=warmup, future_bars=future_bars)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return write_report(out_root / stamp, rows, timeframe, funding_symbol)


def main() -> None:
    parser = argparse.ArgumentParser(description="MoonFace funding-rate edge probe.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT:USDT")
    parser.add_argument("--funding-symbol", default="BTC/USDT:USDT")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--k", type=float, default=1.0)
    parser.add_argument("--m", type=float, default=2.0)
    parser.add_argument("--n-bars", type=int, default=24)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0)
    parser.add_argument("--oos-tail-bars", type=int, default=1095)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--future-bars", type=int, default=48)
    parser.add_argument("--out-root", default="experiments/funding")
    args = parser.parse_args()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(args.years * 365 * _DAY_MS)
    out_dir = run_funding_probe(
        exchange=args.exchange, symbol=args.symbol,
        funding_symbol=args.funding_symbol, start_ms=start_ms, end_ms=now_ms,
        cache_dir=args.cache_dir, timeframe=args.timeframe, k=args.k, m=args.m,
        n_bars=args.n_bars, atr_period=args.atr_period, fee_rate=args.fee_rate,
        slippage=args.slippage, oos_tail_bars=args.oos_tail_bars, warmup=args.warmup,
        future_bars=args.future_bars, out_root=Path(args.out_root))
    print(f"Funding probe report written to {out_dir}")


if __name__ == "__main__":
    main()
