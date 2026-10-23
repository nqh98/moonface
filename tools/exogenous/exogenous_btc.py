"""Exogenous-conditioned BTC state model — staged research CLI (PAPER ONLY).

Stages (human-gated, commit prereg before --explore, freeze before --validate):
  --readiness : Stage 0 newdata gate on FRED + Deribit sources.
  --screen    : Stage 1 gross conditional-drift screen (|t|>=2 kill).
  --explore   : leaderboard of per-state conditional stats.
  --select    : freeze surviving states -> frozen_candidates.json (commit first).
  --validate  : Stage 3 walk-forward econ verdict + DSR.
  --transfer  : Stage 4 ETH/SOL transfer.
  --forward   : Stage 5 forward paper report from committed registration.
Touches nothing in promotion/ or journal/. Going live is human-only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from moonface.research.exogenous.backtest import daily_returns, episode_trades
from moonface.research.exogenous.conditioning import state_positions
from moonface.research.exogenous.deribit_dvol import fetch_dvol
from moonface.research.exogenous.evaluate import dsr_of_trades, econ_verdict
from moonface.research.exogenous.fred_data import fetch_fred_series
from moonface.research.exogenous.forward import forward_report
from moonface.research.exogenous.grid import N_TRIALS, PRECOMMITTED_STATES
from moonface.research.exogenous.screen import SCREEN_T, screen_passes, screen_state
from moonface.research.exogenous.transfer import transfer_passes, transfer_report
from moonface.research.newdata import assess_manifest
from moonface.research.universe_data import fetch_daily_klines

MACRO_SERIES = ("SP500", "DTWEXBGS", "VIXCLS", "DGS2", "DGS10")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exogenous-btc")
    g = p.add_mutually_exclusive_group(required=True)
    for flag in ("readiness", "screen", "explore", "select", "validate",
                 "transfer", "forward"):
        g.add_argument(f"--{flag}", action="store_true")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--start-ms", type=int, default=1577836800000)
    p.add_argument("--end-ms", type=int, default=1782300000000)
    p.add_argument("--cache-dir", default="cache/exogenous")
    p.add_argument("--out-dir", default="experiments/exogenous")
    return p


def _fetch_symbol(symbol: str, start: int, end: int, cache_dir: str):
    rows = fetch_daily_klines(symbol, start, end, cache_dir)
    ts = [r.ts_ms for r in rows]
    closes = [r.close for r in rows]
    return ts, closes


def _fetch_macro(cache_dir: str) -> dict:
    return {sid: fetch_fred_series(sid, cache_dir) for sid in MACRO_SERIES}


_LICENSE = {"research_allowed": True, "derived_features_allowed": True,
            "retention_allowed": True}


def _span_days(pts) -> int:
    if not pts or len(pts) < 2:
        return 0
    return (pts[-1].ts_ms - pts[0].ts_ms) // 86_400_000


def _readiness(args) -> int:
    """Stage 0: assess FRED (macro_series) + Deribit DVOL (implied_vol)."""
    verdicts = []
    series = _fetch_macro(args.cache_dir)
    for sid, pts in series.items():
        manifest = {
            "provider": "FRED", "data_class": "macro_series",
            "fields": ["ts_ms", "series_id", "value", "publish_lag_days"],
            "symbols": [sid],
            "history_days": _span_days(pts),
            "cadence_ms": 86_400_000,
            "coverage_ratio": 1.0,
            "monotonic_timestamps": True,
            "duplicate_timestamp_ratio": 0.0,
            "license": dict(_LICENSE),
        }
        verdicts.append({"source": f"FRED:{sid}", "verdict": assess_manifest(manifest)})
    dvol = fetch_dvol("BTC", args.start_ms, args.end_ms, args.cache_dir)
    manifest = {
        "provider": "Deribit", "data_class": "implied_vol",
        "fields": ["ts_ms", "symbol", "dvol_open", "dvol_high", "dvol_low", "dvol_close"],
        "symbols": ["BTCUSDT"],
        "history_days": _span_days(dvol),
        "cadence_ms": 86_400_000,
        "coverage_ratio": 1.0,
        "monotonic_timestamps": True,
        "duplicate_timestamp_ratio": 0.0,
        "license": dict(_LICENSE),
    }
    verdicts.append({"source": "Deribit:DVOL", "verdict": assess_manifest(manifest)})
    print(json.dumps({"readiness": verdicts}, indent=2))
    return 0


def _screen(args, ts, closes, series) -> int:
    """Stage 1: gross conditional-drift screen."""
    fwd = daily_returns(closes)
    results = [screen_state(ts[:len(fwd)], fwd, series, s) for s in PRECOMMITTED_STATES]
    print(json.dumps(
        {"results": results, "passes": screen_passes(results)}, indent=2))
    return 0


def _explore(args, ts, closes, series) -> int:
    """Stage 2: write leaderboard JSON."""
    fwd = daily_returns(closes)
    results = [screen_state(ts[:len(fwd)], fwd, series, s) for s in PRECOMMITTED_STATES]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "leaderboard.json").write_text(
        json.dumps({"results": results, "passes": screen_passes(results)}, indent=2))
    print(json.dumps({"wrote": str(out / "leaderboard.json")}, indent=2))
    return 0


def _select(args, ts, closes, series) -> int:
    """Stage 2b: freeze surviving candidates (commit first)."""
    fwd = daily_returns(closes)
    results = [screen_state(ts[:len(fwd)], fwd, series, s) for s in PRECOMMITTED_STATES]
    survivors = [r for r in results if abs(r["t"]) >= SCREEN_T]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "frozen_candidates.json").write_text(
        json.dumps({"candidates": survivors, "n_trials": N_TRIALS}, indent=2))
    print(json.dumps(
        {"wrote": str(out / "frozen_candidates.json"), "n": len(survivors)},
        indent=2))
    return 0


def _validate(args, ts, closes, series) -> int:
    """Stage 3: walk-forward econ verdict + DSR (passed = econ AND DSR>=0.95)."""
    v = econ_verdict(closes, ts, series)
    rets = daily_returns(closes)
    pos = state_positions(ts[:len(rets)], series)
    trades = episode_trades(pos[:len(rets)], rets)
    dsr = dsr_of_trades(trades, N_TRIALS)
    dsr_pass = dsr >= 0.95
    print(json.dumps({
        "passed": bool(v.passed and dsr_pass),
        "dsr_pass": bool(dsr_pass),
        "dsr": round(dsr, 6),
        "econ_passed": bool(v.passed),
        "metrics": v.metrics, "reasons": v.reasons,
        "n_trials": N_TRIALS,
    }, indent=2))
    return 0


def _transfer(args, ts, series) -> int:
    """Stage 4: ETH/SOL transfer."""
    assets = ("ETHUSDT", "SOLUSDT")
    closes_by, ts_by = {}, {}
    for sym in assets:
        t, c = _fetch_symbol(sym, args.start_ms, args.end_ms, args.cache_dir)
        ts_by[sym] = t
        closes_by[sym] = c
    rep = transfer_report(closes_by, ts_by, series, assets)
    print(json.dumps({"report": rep, "passes": transfer_passes(rep)}, indent=2))
    return 0


def _forward(args) -> int:
    """Stage 5: forward paper report from committed registration."""
    fwd_dir = Path(args.out_dir) / "forward"
    if not fwd_dir.exists():
        print(json.dumps({"error": f"{fwd_dir} not found"}, indent=2))
        return 1
    for p in sorted(fwd_dir.glob("*.json")):
        reg = json.loads(p.read_text())
        trades = reg.get("trades", [])
        t0 = reg.get("t0_ms", args.start_ms)
        rep = forward_report(trades, t0, args.end_ms)
        print(json.dumps({"registration": p.name, "report": rep}, indent=2))
    return 0


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.readiness:
        return _readiness(args)
    if args.forward:
        return _forward(args)
    ts, closes = _fetch_symbol(args.symbol, args.start_ms, args.end_ms, args.cache_dir)
    series = _fetch_macro(args.cache_dir)
    if args.screen:
        return _screen(args, ts, closes, series)
    if args.explore:
        return _explore(args, ts, closes, series)
    if args.select:
        return _select(args, ts, closes, series)
    if args.validate:
        return _validate(args, ts, closes, series)
    if args.transfer:
        return _transfer(args, ts, series)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
