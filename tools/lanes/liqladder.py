#!/usr/bin/env python
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.data.series import align_metric, fetch_metrics_history
from moonface.research.liqladder import (ATR_K, ATR_PERIOD, A_THR, BIN_W,
                                         DELTA, DENSE_Q, MIN_ASSETS,
                                         MIN_EVENTS, MMR, TIER_W, TIERS,
                                         detect_events, event_net_returns,
                                         liqladder_verdict, nonoverlap_events,
                                         pooled)
from moonface.features.oi_features import asset_stats, fresh_coverage
from moonface.research.universe_data import fetch_perp_candles
from tools.lanes.oibuild_study import candidates_from_caches

_DAY_MS = 86_400_000

DESIGN = {
    "interval": "1h",
    "h": 6,
    "cost": 0.001,
    "n_confirm": 16,
    "min_assets": MIN_ASSETS,
    "min_events": MIN_EVENTS,
    "min_coverage": 0.8,
    "oi_field": "sum_open_interest",
    "ratio_field": "count_long_short_ratio",
    "bin_w": BIN_W,
    "tiers": list(TIERS),
    "tier_w": TIER_W,
    "mmr": MMR,
    "delta": DELTA,
    "a_thr": A_THR,
    "dense_q": DENSE_Q,
    "atr_period": ATR_PERIOD,
    "atr_k": ATR_K,
    "discovery": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "window_days": 730,
    "top_k_candidates": 24,
    "vol_days": 30,
    "min_history_days": 365,
}


def resolve_candidates(cache_dir: str, window_start: int) -> list[str]:
    return candidates_from_caches(
        cache_dir, window_start, exclude=set(DESIGN["discovery"]),
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


def _asset_result(candles, oi, ls_ratio, cfg):
    raw = detect_events(candles, oi, ls_ratio, delta=cfg["delta"],
                        a_thr=cfg["a_thr"], dense_q=cfg["dense_q"],
                        atr_period=cfg["atr_period"], atr_k=cfg["atr_k"])
    events = nonoverlap_events(raw, cfg["h"])
    rets = event_net_returns(candles, events, h=cfg["h"], cost=cfg["cost"])
    return events, rets, asset_stats(rets)


def run_analysis(cfg: dict, fetch_candles, fetch_metrics,
                 out_dir: Path) -> dict:
    verdict_path = out_dir / "verdict.json"
    if verdict_path.exists():
        sys.exit(f"{verdict_path} already exists; the analysis is one-touch")
    accepted: list[dict] = []
    skipped: list[str] = []
    print(f"walking candidates: target {cfg['n_confirm']} confirmation assets,"
          f" min coverage {cfg['min_coverage']:.0%}")
    for sym in cfg["candidates"]:
        if len(accepted) >= cfg["n_confirm"]:
            break
        candles = fetch_candles(sym, cfg["start_ms"], cfg["end_ms"])
        rows = fetch_metrics(sym, cfg["start_ms"], cfg["end_ms"])
        oi_points = [(ts, f[cfg["oi_field"]]) for ts, f in rows
                     if cfg["oi_field"] in f]
        ratio_points = [(ts, f[cfg["ratio_field"]]) for ts, f in rows
                        if cfg["ratio_field"] in f]
        coverage = fresh_coverage(candles, oi_points)
        if not candles or coverage < cfg["min_coverage"]:
            skipped.append(sym)
            reason = "no candles" if not candles else (
                f"coverage {coverage:.0%} < {cfg['min_coverage']:.0%}")
            print(f"  {sym}: skipped ({reason})")
            continue
        oi = align_metric(candles, oi_points)
        ls_ratio = align_metric(candles, ratio_points)
        accepted.append({"sym": sym, "candles": candles, "oi": oi,
                         "ls_ratio": ls_ratio})
        print(f"  {sym}: accepted ({len(candles)} bars, coverage {coverage:.0%})")

    per_asset = []
    for a in accepted:
        events, rets, stats = _asset_result(a["candles"], a["oi"],
                                            a["ls_ratio"], cfg)
        per_asset.append({"sym": a["sym"], **stats, "_events": events,
                          "_rets": rets, "_a": a})
        print(f"  {a['sym']}: {stats['n']} non-overlapping events,"
              f" mean net continuation {stats['mean']:+.6f}")
    evaluable = [s for s in per_asset if s["n"] >= cfg["min_events"]]
    print(f"evaluable: {len(evaluable)}/{len(accepted)} assets"
          f" (>= {cfg['min_events']} events each);"
          f" skipped for coverage: {len(skipped)}")

    halves = {"first": [], "second": []}
    for s in evaluable:
        mid = len(s["_a"]["candles"]) // 2
        first_events = [e for e in s["_events"] if e[0] < mid]
        second_events = [e for e in s["_events"] if e[0] >= mid]
        halves["first"].append(asset_stats(event_net_returns(
            s["_a"]["candles"], first_events, h=cfg["h"], cost=cfg["cost"])))
        halves["second"].append(asset_stats(event_net_returns(
            s["_a"]["candles"], second_events, h=cfg["h"], cost=cfg["cost"])))
    loo = [sum(x["mean"] for x in evaluable if x is not s) / max(1, len(evaluable) - 1)
           for s in evaluable]
    robustness = {
        "time_first_half": pooled(halves["first"]),
        "time_second_half": pooled(halves["second"]),
        "leave_one_out_pooled_mean": {
            "min": min(loo) if loo else 0.0,
            "max": max(loo) if loo else 0.0,
        },
    }
    verdict = liqladder_verdict(
        [{k: s[k] for k in ("n", "mean", "t")} for s in evaluable],
        robustness, min_assets=cfg["min_assets"])

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
        "robustness": robustness,
        "registration_hash": registration_hash(cfg),
        "data_fingerprint": data_fingerprint(series_by_key),
        "code_hash": code_hash(["tools/lanes/liqladder.py",
                               "src/moonface/features/oi_features.py",
                               "src/moonface/research/liqladder.py"]),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(json.dumps(out, indent=2))
    (out_dir / "report.md").write_text(_render(cfg, out))
    return out


def _render(cfg: dict, v: dict) -> str:
    lines = [
        "# Liqladder liquidation-ladder magnet verdict",
        "",
        f"- generated: {v['generated_utc']}",
        f"- **verdict: {v['verdict']}** - {v['reason']}",
        f"- evaluable assets: {v['m_assets']} (skipped: {len(v['skipped'])})",
        f"- co-primary: k_positive = {v['k_positive']}, Stouffer Z = {v['stouffer_z']}, pooled mean = {v['pooled_mean']}",
        "",
        f"## Per-asset (h={cfg['h']} bars, net of cost)",
        "",
        "| asset | events | mean net continuation | t |",
        "|---|---|---|---|",
    ]
    for a in v["assets"]:
        lines.append(f"| {a['sym']} | {a['n']} | {a['mean']:.6f} | {a['t']:.2f} |")
    lines += ["", "## Robustness", "", "```json",
              json.dumps(v["robustness"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/liqladder")
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

    def fetch_metrics(sym, start, end):
        return fetch_metrics_history(sym, start, end, args.cache_dir)

    v = run_analysis(cfg, fetch_candles, fetch_metrics, out_dir)
    print(f"[{v['verdict']}] {v['reason']}")
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
