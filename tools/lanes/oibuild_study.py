#!/usr/bin/env python
# tools/oibuild_study.py
"""Pooled cross-asset OI-build mechanism study.

Frozen design: experiments/oibuild_study/PREREGISTRATION.md. `register`
resolves the candidate queue from the cached daily-kline volume data and
freezes everything; `run` downloads what's missing (resumable — a crash
before the verdict spends nothing) and performs the one-touch analysis.
Mechanism science only: no exits, sizing, or optimization of any kind."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from statistics import fmean

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.edge.positioning_signals import (
    make_oi_build_momentum, make_toptrader_follow)
from moonface.data.series import fetch_metrics_history
from moonface.research.universe_data import (fetch_perp_candles,
                                             load_daily_cache)
from moonface.data.series import align_metric as _align
from moonface.features.oi_features import (asset_stats, binom_p_geq,
                                             event_returns, fresh_coverage,
                                             nonoverlap, select_universe,
                                             stouffer, verdict_from)

_DAY_MS = 86_400_000

DESIGN = {
    "window": 180, "lookback": 6, "z_thr": 1.5, "h": 24,
    "h_secondary": [6, 48], "lookback_secondary": 24,
    "cost": 0.001,  # round-trip fraction, the program's COST_FRACTION
    "n_confirm": 16, "min_assets": 8, "min_events": 10, "min_coverage": 0.8,
    "metrics_field": "sum_open_interest",
    "discovery": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "window_days": 730, "top_k_candidates": 24,
    "vol_days": 30, "min_history_days": 365,
}


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


# The uni1d caches begin at the 3y xsection window, and daily klines are
# UTC-midnight aligned, so a symbol listed long before the cache still has
# its first cached row up to ~2 days after (cache boundary + alignment).
# The listing-age floor must absorb that resolution limit, or symbols with
# truncated history get excluded wholesale.
_CACHE_BOUNDARY_TOLERANCE_DAYS = 2


def candidates_from_caches(cache_dir: str, window_start: int,
                           exclude: set[str], top_k: int, vol_days: int,
                           min_history_days: int) -> list[str]:
    daily = {}
    for p in sorted(Path(cache_dir).glob("uni1d_*.csv")):
        sym = p.stem.removeprefix("uni1d_")
        rows = load_daily_cache(cache_dir, sym)
        if rows:
            daily[sym] = rows
    return select_universe(
        daily, window_start, exclude=exclude, top_k=top_k, vol_days=vol_days,
        min_history_days=(min_history_days
                          - _CACHE_BOUNDARY_TOLERANCE_DAYS))


def _candidates_from_caches(cache_dir: str, window_start: int) -> list[str]:
    return candidates_from_caches(
        cache_dir, window_start, exclude=set(DESIGN["discovery"]),
        top_k=DESIGN["top_k_candidates"], vol_days=DESIGN["vol_days"],
        min_history_days=DESIGN["min_history_days"])


def _events(candles, feature, cfg: dict, lookback: int) -> list[tuple[int, str]]:
    """Raw events via the pre-registered generator: change-momentum (OI
    build) or level-follow (the toptrader/taker machinery, reused verbatim
    for the book-depth imbalance study; level generators have no lookback)."""
    if cfg.get("generator", "change_momentum") == "level_follow":
        params = {"window": cfg["window"], "z_thr": cfg["z_thr"]}
        return make_toptrader_follow(feature)(candles, params)
    params = {"window": cfg["window"], "lookback": lookback,
              "z_thr": cfg["z_thr"]}
    return make_oi_build_momentum(feature)(candles, params)


def _evaluate(candles, feature, cfg: dict, lookback: int,
              h: int) -> list[float]:
    events = _events(candles, feature, cfg, lookback)
    closes = [c.close for c in candles]
    return event_returns(closes, nonoverlap(events, h), h)


def _pooled(stats: list[dict]) -> dict:
    if not stats:
        return {"m": 0, "k": 0, "p_sign": 1.0, "z": 0.0, "pooled_mean": 0.0}
    k = sum(1 for s in stats if s["mean"] > 0)
    return {"m": len(stats), "k": k, "p_sign": binom_p_geq(k, len(stats)),
            "z": stouffer([s["t"] for s in stats]),
            "pooled_mean": fmean([s["mean"] for s in stats])}


def run_analysis(cfg: dict, fetch_candles, fetch_metric,
                 out_dir: Path) -> dict:
    verdict_path = out_dir / "verdict.json"
    if verdict_path.exists():
        sys.exit(f"{verdict_path} already exists; the analysis is one-touch"
                 " and this study is closed")
    start, end = cfg["start_ms"], cfg["end_ms"]
    accepted: list[dict] = []   # name, candles, feature
    skipped: list[str] = []
    for sym in cfg["candidates"]:
        if len(accepted) >= cfg["n_confirm"]:
            break
        candles = fetch_candles(sym, start, end)
        points = fetch_metric(sym, start, end)
        coverage = fresh_coverage(candles, points,
                                  max_age_ms=cfg.get("max_age_ms", _DAY_MS))
        if not candles or coverage < cfg["min_coverage"]:
            skipped.append(sym)
            print(f"  {sym}: skipped (insufficient fresh metrics coverage)")
            continue
        feature = _align(candles, points)
        accepted.append({"sym": sym, "candles": candles, "feature": feature})
        print(f"  {sym}: accepted ({len(candles)} bars)")

    per_asset: list[dict] = []
    for a in accepted:
        rets = _evaluate(a["candles"], a["feature"], cfg, cfg["lookback"],
                         cfg["h"])
        per_asset.append({"sym": a["sym"], **asset_stats(rets),
                          "_rets": rets, "_a": a})
    evaluable = [s for s in per_asset if s["n"] >= cfg["min_events"]]
    verdict = verdict_from([{k: s[k] for k in ("n", "mean", "t")}
                            for s in evaluable],
                           min_assets=cfg["min_assets"])

    desc: dict = {}
    for h2 in cfg["h_secondary"]:
        stats = [asset_stats(_evaluate(a["candles"], a["feature"], cfg,
                                       cfg["lookback"], h2))
                 for a in accepted]
        desc[f"h_{h2}"] = _pooled([s for s in stats
                                   if s["n"] >= cfg["min_events"]])
    if cfg.get("generator", "change_momentum") != "level_follow":
        lb2 = cfg["lookback_secondary"]
        stats = [asset_stats(_evaluate(a["candles"], a["feature"], cfg, lb2,
                                       cfg["h"]))
                 for a in accepted]
        desc[f"lookback_{lb2}"] = _pooled([s for s in stats
                                           if s["n"] >= cfg["min_events"]])
    desc["net_of_cost"] = _pooled([
        asset_stats([r - cfg["cost"] for r in s["_rets"]])
        for s in evaluable])
    half = len(evaluable) // 2
    desc["liquidity_upper_half"] = _pooled(evaluable[:half])
    desc["liquidity_lower_half"] = _pooled(evaluable[half:])
    if evaluable:
        loo = [fmean([x["mean"] for x in evaluable if x is not s])
               for s in evaluable]
        desc["leave_one_out_pooled_mean"] = {"min": min(loo), "max": max(loo)}
    halves = {"first": [], "second": []}
    for s in evaluable:
        mid = len(s["_a"]["candles"]) // 2
        events = nonoverlap(_events(s["_a"]["candles"], s["_a"]["feature"],
                                    cfg, cfg["lookback"]), cfg["h"])
        closes = [c.close for c in s["_a"]["candles"]]
        halves["first"].append(asset_stats(event_returns(
            closes, [e for e in events if e[0] < mid], cfg["h"])))
        halves["second"].append(asset_stats(event_returns(
            closes, [e for e in events if e[0] >= mid], cfg["h"])))
    desc["time_first_half"] = _pooled(halves["first"])
    desc["time_second_half"] = _pooled(halves["second"])

    discovery_stats = []
    for sym in cfg["discovery"]:
        candles = fetch_candles(sym, start, end)
        points = fetch_metric(sym, start, end)
        if not candles:
            continue
        feature = _align(candles, points)
        rets = _evaluate(candles, feature, cfg, cfg["lookback"], cfg["h"])
        discovery_stats.append({"sym": sym, **asset_stats(rets)})

    from moonface.core.provenance import (code_hash, data_fingerprint,
                                          registration_hash)
    from moonface.core.stats import series_fingerprint

    series_by_key = {a["sym"]: series_fingerprint(a["candles"]) for a in accepted}

    out = {
        **verdict,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "assets": [{k: s[k] for k in ("sym", "n", "mean", "t")}
                   for s in per_asset],
        "skipped": skipped,
        "descriptive": desc,
        "discovery_set_contaminated": discovery_stats,
        "registration_hash": registration_hash(cfg),
        "data_fingerprint": data_fingerprint(series_by_key),
        "code_hash": code_hash(["tools/lanes/oibuild_study.py",
                               "src/moonface/features/oi_features.py"]),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(json.dumps(out, indent=2))
    (out_dir / "report.md").write_text(_render(cfg, out))
    return out


def _render(cfg: dict, v: dict) -> str:
    lines = [
        "# OI-build mechanism study — pooled cross-asset verdict",
        "",
        f"- generated: {v['generated_utc']}",
        f"- **verdict: {v['verdict']}** — {v['reason']}",
        f"- evaluable assets: {v['m_assets']}"
        f" (skipped for coverage: {len(v['skipped'])})",
        f"- co-primary: sign test p = {v['p_sign']},"
        f" Stouffer Z = {v['stouffer_z']},"
        f" pooled mean = {v['pooled_mean']}",
        "",
        "## Per-asset (confirmation set, primary endpoint"
        f" h={cfg['h']} bars, gross)",
        "",
        "| asset | events | mean directional ret | t |",
        "|---|---|---|---|",
    ]
    for a in v["assets"]:
        lines.append(f"| {a['sym']} | {a['n']} | {a['mean']:.6f}"
                     f" | {a['t']:.2f} |")
    lines += ["", "## Pre-registered descriptive analyses", "", "```json",
              json.dumps(v["descriptive"], indent=2), "```", "",
              "## Discovery set (BTC/ETH/SOL — contaminated, excluded from"
              " evidence)", "", "```json",
              json.dumps(v["discovery_set_contaminated"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/oibuild_study")
    p.add_argument("--cache-dir", default=".backtest_cache")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("register", help="freeze window, universe, and endpoints")
    sub.add_parser("run", help="resumable download + one-touch analysis")
    args = p.parse_args()
    out_dir = Path(args.out)
    if args.command == "register":
        now = int(time.time() * 1000)
        candidates = _candidates_from_caches(
            args.cache_dir, now - DESIGN["window_days"] * _DAY_MS)
        cmd_register(out_dir, candidates, now_ms=now)
        return
    reg_path = out_dir / "registration.json"
    if not reg_path.exists():
        sys.exit("no registration; run `register` first")
    cfg = json.loads(reg_path.read_text())

    def fetch_candles(sym, start, end):
        return fetch_perp_candles(sym, "4h", start, end, args.cache_dir)

    def fetch_metric(sym, start, end):
        field = cfg["metrics_field"]
        raw = fetch_metrics_history(sym, start, end, args.cache_dir)
        return [(ts, f[field]) for ts, f in raw if field in f]

    v = run_analysis(cfg, fetch_candles, fetch_metric, out_dir)
    print(f"[{v['verdict']}] {v['reason']}")
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
