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
from moonface.research.sizing import split_research_tail
from moonface.research.edge.exit_score import ENTRY_SPECS_BY_TF, exit_r_streams
from moonface.core.exits import horizon_hold
from moonface.research.sizing import SizingReport, size_report
from moonface.core.models import Candle

_DAY_MS = 86_400_000
# Pre-committed exit for the sizing run: the n_bars=24 validation hold (uniform across
# all entries), chosen without selecting on the OOS fold. See the design doc.
SIZING_EXIT_PARAMS = {"n_bars": 24, "atr_period": 14}


def partition(
    research_pairs: list[tuple[int, float]],
    tail_pairs: list[tuple[int, float]],
) -> tuple[list[float], list[float], float, float]:
    """Strip timestamps to bare R-streams; return streams + span-days per side."""
    def span_days(rows: list[tuple[int, float]]) -> float:
        if len(rows) < 2:
            return 0.0
        return (rows[-1][0] - rows[0][0]) / _DAY_MS

    return ([r for _, r in research_pairs], [r for _, r in tail_pairs],
            span_days(research_pairs), span_days(tail_pairs))


def render_markdown(
    results: list[tuple[str, dict, SizingReport]], timeframe: str,
) -> str:
    lines = [
        "# MoonFace Position Sizing Report",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframe: {timeframe}",
        f"- exit: horizon_hold {SIZING_EXIT_PARAMS}",
        "",
        "| entry | params | chosen f | rsch term | rsch CAGR | rsch MC dd% | "
        "tail term | tail CAGR | tail MC dd% | tail n | reject |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, params, rep in results:
        lines.append(
            f"| {name} | {params} | {rep.chosen_f} | "
            f"{rep.research.terminal} | {rep.research.cagr} | "
            f"{rep.research_mc_drawdown_pct} | "
            f"{rep.tail.terminal} | {rep.tail.cagr} | {rep.tail_mc_drawdown_pct} | "
            f"{rep.tail.n_trades} | {rep.reject_reason} |")
    return "\n".join(lines) + "\n"


def write_sizing_report(
    out_dir: Path, results: list[tuple[str, dict, SizingReport]], timeframe: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timeframe": timeframe,
        "exit": {"name": "horizon_hold", "params": SIZING_EXIT_PARAMS},
        "entries": [
            {"entry": name, "entry_params": params, "report": asdict(rep)}
            for name, params, rep in results
        ],
    }
    (out_dir / "sizing.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "sizing.md").write_text(
        render_markdown(results, timeframe), encoding="utf-8")
    return out_dir


def run_sizing(
    exchange: str, symbol: str, start_ms: int, end_ms: int, cache_dir: str,
    timeframe: str, oos_tail_bars: int, warmup: int, future_bars: int,
    dd_cap: float, percentile: float, resamples: int, seed: int, out_root: Path,
) -> Path:
    cache = OhlcvCache(cache_dir)
    candles: list[Candle] = fetch_history(exchange, symbol, timeframe,
                                          start_ms, end_ms, cache)
    try:
        entry_specs = ENTRY_SPECS_BY_TF[timeframe]
    except KeyError:
        raise SystemExit(
            f"no entry set defined for timeframe {timeframe!r}; "
            f"known: {sorted(ENTRY_SPECS_BY_TF)}")
    tail_start = split_research_tail(candles, oos_tail_bars, warmup, future_bars)

    results: list[tuple[str, dict, SizingReport]] = []
    for entry_name, generator, entry_params in entry_specs:
        entries = generator(candles, entry_params)
        research_pairs, tail_pairs = exit_r_streams(
            candles, entries, horizon_hold, SIZING_EXIT_PARAMS, tail_start)
        research_rs, tail_rs, rsd, tsd = partition(research_pairs, tail_pairs)
        rep = size_report(research_rs, tail_rs, dd_cap=dd_cap, percentile=percentile,
                          resamples=resamples, seed=seed,
                          research_span_days=rsd, tail_span_days=tsd)
        results.append((entry_name, entry_params, rep))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return write_sizing_report(out_root / stamp, results, timeframe)


def main() -> None:
    parser = argparse.ArgumentParser(description="MoonFace Phase 3 position sizing.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT:USDT")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--oos-tail-bars", type=int, default=1095)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--future-bars", type=int, default=48)
    parser.add_argument("--dd-cap", type=float, default=0.20)
    parser.add_argument("--percentile", type=float, default=95)
    parser.add_argument("--resamples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--out-root", default="experiments/sizing")
    args = parser.parse_args()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(args.years * 365 * _DAY_MS)
    out_dir = run_sizing(
        exchange=args.exchange, symbol=args.symbol, start_ms=start_ms, end_ms=now_ms,
        cache_dir=args.cache_dir, timeframe=args.timeframe,
        oos_tail_bars=args.oos_tail_bars, warmup=args.warmup,
        future_bars=args.future_bars, dd_cap=args.dd_cap, percentile=args.percentile,
        resamples=args.resamples, seed=args.seed, out_root=Path(args.out_root))
    print(f"Sizing report written to {out_dir}")


if __name__ == "__main__":
    main()
