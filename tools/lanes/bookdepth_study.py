#!/usr/bin/env python
# tools/bookdepth_study.py
"""Pooled cross-asset book-depth imbalance mechanism study.

Frozen design: experiments/bookdepth_study/PREREGISTRATION.md. The analysis
harness (universe walk, freshness gate, per-asset stats, sign-test/Stouffer
pooling, tripartite one-touch verdict) is tools/oibuild_study.run_analysis
with the level-follow generator; only the information set is new. The
hypothesis comes from external microstructure literature, so there is no
contaminated discovery set. Mechanism science only — no trading."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools.* sibling

from moonface.data.orderbook import fetch_bookdepth_history
from moonface.features.orderbook_features import imbalance_points
from moonface.research.universe_data import fetch_perp_candles
from tools.lanes.oibuild_study import candidates_from_caches, run_analysis

_DAY_MS = 86_400_000

DESIGN = {
    "generator": "level_follow",
    "interval": "1h",
    "window": 180, "z_thr": 1.5,
    # level generators have no lookback; the keys exist because the shared
    # harness requires them and are inert by design (see pre-registration)
    "lookback": 0, "lookback_secondary": 0,
    "h": 6, "h_secondary": [1, 24],
    "max_age_ms": 3_600_000,  # snapshots are ~30s apart; 1h staleness gate
    "cost": 0.001,
    "n_confirm": 16, "min_assets": 8, "min_events": 10, "min_coverage": 0.8,
    "discovery": [],  # external-literature prior: no contaminated assets
    "window_days": 730, "top_k_candidates": 24,
    "vol_days": 30, "min_history_days": 365,
}


def resolve_candidates(cache_dir: str, window_start: int) -> list[str]:
    return candidates_from_caches(
        cache_dir, window_start, exclude=set(),
        top_k=DESIGN["top_k_candidates"], vol_days=DESIGN["vol_days"],
        min_history_days=DESIGN["min_history_days"])


def cmd_register(out_dir: Path, candidates: list[str],
                 now_ms: int | None = None) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    reg = dict(DESIGN)
    reg["end_ms"] = now
    reg["start_ms"] = now - DESIGN["window_days"] * _DAY_MS
    reg["candidates"] = candidates
    reg["registered_utc"] = dt.datetime.fromtimestamp(
        now / 1000, dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} ({len(candidates)} candidates frozen)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/bookdepth_study")
    p.add_argument("--cache-dir", default=".backtest_cache")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("register", help="freeze window, universe, and endpoints")
    sub.add_parser("run", help="resumable download + one-touch analysis")
    args = p.parse_args()
    out_dir = Path(args.out)
    if args.command == "register":
        now = int(time.time() * 1000)
        candidates = resolve_candidates(
            args.cache_dir, now - DESIGN["window_days"] * _DAY_MS)
        cmd_register(out_dir, candidates, now_ms=now)
        return
    reg_path = out_dir / "registration.json"
    if not reg_path.exists():
        sys.exit("no registration; run `register` first")
    cfg = json.loads(reg_path.read_text())

    def fetch_candles(sym, start, end):
        return fetch_perp_candles(sym, cfg["interval"], start, end,
                                  args.cache_dir)

    def fetch_metric(sym, start, end):
        return imbalance_points(
            fetch_bookdepth_history(sym, start, end, args.cache_dir))

    v = run_analysis(cfg, fetch_candles, fetch_metric, out_dir)
    print(f"[{v['verdict']}] {v['reason']}")
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
