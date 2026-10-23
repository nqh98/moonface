# tools/engine/engine_honest_report.py
"""Live-faithful honest verdict report for the confluence engine.

Replays the full window through the SAME (now rolling-window, live-faithful)
`tools.engine.engine_backtest.replay` path, then emits the committed scorecard plus the
three framing-correction blocks (recency, outlier dependence, cost sensitivity).
Reproducible from committed code — this supersedes the throwaway /tmp harnesses.
NOT a DSR/pass gate and NOT an edge claim: it tells you *how* a net-R number is
earned so a thin headline cannot hide a frozen sub-period or outlier dependence.

Usage:
  .venv/bin/python -m tools.engine.engine_honest_report \
      --start-ms 1577836800000 --end-ms 1782316800000 --out /tmp/report.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from moonface.data.bundle import load_bundle
from moonface.core.metrics import (MAX_LEVERAGE,
                                         equity_summary_from_returns)
from moonface.models.engine.config import engine_hash, load_engine_config
from moonface.models.engine.honesty import (cost_stress, outlier_dependence,
                                            recency_breakdown)
from moonface.models.engine.scorecard import engine_scorecard
from tools.engine.engine_backtest import replay

LABEL = "engine paper — disciplined heuristic, no validated-edge claim"


def build_report(cfg, candles: list, warmup: int) -> dict:
    """Pure: replay candles (no fetch) and assemble the honest verdict report."""
    entries = replay(cfg, candles, warmup)
    sc = engine_scorecard(entries, cfg)

    dec: dict[str, int] = {}
    act: dict[str, int] = {}
    for e in entries:
        dec[e["decision"]] = dec.get(e["decision"], 0) + 1
        act[e["action"]] = act.get(e["action"], 0) + 1

    trades = [(e["ts_ms"], float(e["realized_r"]),
               float(e["atr_frac"] or 0.0), float(e["fraction"] or 0.0))
              for e in entries
              if e["action"] == "EXIT" and e["realized_r"] is not None]
    rs = [r for _, r, _, _ in trades]

    first_ts, last_ts = candles[0].timestamp_ms, candles[-1].timestamp_ms
    span = last_ts - first_ts
    year_ms = 365 * 24 * 3_600_000
    years = span / year_ms if year_ms else 0.0
    bars_in_pos = act.get("OPEN", 0) + act.get("HOLD", 0)
    returns = [min(fr, MAX_LEVERAGE * af) * r for _, r, af, fr in trades]
    eq = equity_summary_from_returns(returns)

    return {
        "data": {
            "symbol": cfg.asset["symbol"], "timeframe": cfg.asset["timeframe"],
            "exchange": cfg.asset["exchange"], "candles": len(candles),
            "start_utc": datetime.fromtimestamp(
                first_ts / 1000, timezone.utc).isoformat(),
            "end_utc": datetime.fromtimestamp(
                last_ts / 1000, timezone.utc).isoformat(),
        },
        "engine_version": engine_hash(cfg),
        "rolling_window_bars": cfg.lookback_bars,
        "scorecard": sc,
        "decision_counts": dec,
        "action_counts": act,
        "signal_frequency": {
            "years": round(years, 3), "bar_evals": len(entries),
            "closed_trades": len(trades),
            "trades_per_year": round(len(trades) / years, 3) if years else 0.0,
            "bars_in_position": bars_in_pos,
            "pct_time_in_position": (round(bars_in_pos / len(entries), 4)
                                     if entries else 0.0),
            "avg_bars_per_trade": (round(bars_in_pos / len(trades), 2)
                                   if trades else 0.0),
        },
        "recency": recency_breakdown(trades, first_ts, last_ts),
        "cost_sensitivity": cost_stress(trades),
        "outlier_dependence": outlier_dependence(rs),
        "equity": {"net_return": eq.net_return,
                   "max_drawdown": eq.max_drawdown, "mar": eq.mar},
        "label": LABEL,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine-honest-report")
    p.add_argument("--engine", default="promotion/engine.json")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--warmup", type=int, default=400)
    p.add_argument("--out", default=None)
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_engine_config(args.engine)
    bundle = load_bundle(cfg.asset, args.start_ms, args.end_ms, args.cache_dir)
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
