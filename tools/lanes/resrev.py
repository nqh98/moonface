#!/usr/bin/env python
# tools/resrev.py
"""Cross-sectional short-term residual reversal over the USDT-perp universe.

Reopening cycle 4 (experiments/resrev/PREREGISTRATION.md). Discipline mirrors
xsection/bab: `register` freezes the window, fence, and the single construction
before any data is seen; `run` is one-touch. A cost-first pre-screen runs before
the standard ladder — a gross effect 10x under cost is not tradeable. Signal
discovery only, no trading."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.universe_data import (fetch_daily_klines,
                                             fetch_funding_rates,
                                             list_um_perp_symbols)
from moonface.research.ladder import DSR_THRESHOLD
from moonface.core.metrics import deflated_sharpe
from moonface.research.resrev import mean_z, simulate
from moonface.research.xsection import build_universe, gate_construction

_DAY_MS = 86_400_000
YEARS = 3.0
LOCKBOX_FRACTION = 0.2
SCREEN_FRACTION = 0.7  # research-window split for the cost-first pre-screen

REGISTRATION = {
    "top_n": 20,
    "decile": 10,
    "lookback_days": 60,
    "rebalance_days": 1,
    "fee": 0.0005,  # taker, per side of traded notional
    "min_history_days": 365,
    "vol_days": 30,
    "n_trials": 1,
    "constructions": [
        {"name": "resrev_1", "lookback_days": 60},
    ],
}


def cmd_register(out_dir: Path, now_ms: int | None = None) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the registration is frozen —"
                 " a changed design needs a new experiment directory")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    reg = dict(REGISTRATION)
    reg["start_ms"] = now - int(YEARS * 365 * _DAY_MS)
    reg["end_ms"] = now
    reg["fence_ts"] = now - int(YEARS * 365 * _DAY_MS * LOCKBOX_FRACTION)
    reg["registered_utc"] = dt.datetime.fromtimestamp(
        now / 1000, dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} (window frozen, lockbox tail ="
          f" final {LOCKBOX_FRACTION:.0%})")


def _funding_day_sums(points: list[tuple[int, float]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for ts, rate in points:
        day = (ts // _DAY_MS) * _DAY_MS
        out[day] = out.get(day, 0.0) + rate
    return out


def _universe_union(daily: dict, cfg: dict) -> set[str]:
    members: set[str] = set()
    seen: set[tuple[int, int]] = set()
    ts = cfg["start_ms"]
    while ts < cfg["end_ms"]:
        d = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)
        if (d.year, d.month) not in seen:
            seen.add((d.year, d.month))
            members.update(build_universe(
                daily, ts, cfg["top_n"], cfg["min_history_days"],
                cfg["vol_days"]))
        ts += max(1, cfg["rebalance_days"]) * _DAY_MS
    return members


def _cost_first(daily, funding, cfg, lookback):
    """Gross (fee=0) vs net (registered fee) research-window mean + Z. The
    research window is everything before the fence; the pre-screen passes when
    the net mean is positive."""
    def series(fee):
        return simulate(daily, funding, lookback_days=lookback,
                        start_ms=cfg["start_ms"], end_ms=cfg["end_ms"],
                        top_n=cfg["top_n"], decile=cfg["decile"],
                        rebalance_days=cfg["rebalance_days"], fee=fee,
                        min_history_days=cfg["min_history_days"],
                        vol_days=cfg["vol_days"])
    gross = [r for ts, r in series(0.0) if ts < cfg["fence_ts"]]
    net_full = series(cfg["fee"])
    net = [r for ts, r in net_full if ts < cfg["fence_ts"]]
    g_mean, g_z = mean_z(gross)
    n_mean, n_z = mean_z(net)
    return net_full, {
        "gross_mean": round(g_mean, 8), "gross_z": round(g_z, 4),
        "net_mean": round(n_mean, 8), "net_z": round(n_z, 4),
        "cost_first_pass": n_mean > 0.0,
    }


def run_pipeline(cfg: dict, symbols: list[str], fetch_daily, fetch_funding,
                 out_dir: Path) -> dict:
    verdict_path = out_dir / "verdict.json"
    if verdict_path.exists():
        sys.exit(f"{verdict_path} already exists; the lockbox tail is spent —"
                 " this experiment is closed")
    start, end = cfg["start_ms"], cfg["end_ms"]
    daily = {}
    for sym in symbols:
        rows = fetch_daily(sym, start, end)
        if rows:
            daily[sym] = rows
    members = _universe_union(daily, cfg)
    funding = {sym: _funding_day_sums(fetch_funding(sym, start, end))
               for sym in sorted(members)}
    results = []
    for c in cfg["constructions"]:
        net_full, cost = _cost_first(daily, funding, cfg, c["lookback_days"])
        row = {**c, **cost, "dsr": None}
        if cost["cost_first_pass"]:
            fence_idx = sum(1 for ts, _ in net_full if ts < cfg["fence_ts"])
            row.update(gate_construction([r for _, r in net_full], fence_idx))
        results.append(row)
    trial_srs = [r["research_sharpe"] for r in results if "research_sharpe" in r]
    any_pass = False
    for r in results:
        if not (r.get("cost_first_pass") and r.get("stage1_pass")
                and r.get("stage2_pass")):
            continue
        r["dsr"] = round(deflated_sharpe(
            r["research_sharpe"], r["research_days"], r["research_skew"],
            r["research_kurtosis"], trial_srs, cfg["n_trials"]), 6)
        r["stage3_pass"] = r["dsr"] >= DSR_THRESHOLD
        if r["stage3_pass"] and r.get("stage4_pass"):
            any_pass = True
    verdict = {
        "status": "closed_positive" if any_pass else "closed_negative",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "universe_symbols": len(daily),
        "funding_symbols": len(funding),
        "constructions": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(json.dumps(verdict, indent=2))
    (out_dir / "report.md").write_text(_render_report(cfg, verdict))
    return verdict


def _render_report(cfg: dict, verdict: dict) -> str:
    lines = [
        "# resrev v1 — cross-sectional short-term residual reversal",
        "",
        f"- generated: {verdict['generated_utc']}",
        f"- status: **{verdict['status']}**",
        f"- symbols with data: {verdict['universe_symbols']}"
        f" (funding fetched for {verdict['funding_symbols']})",
        f"- frozen window: {cfg['start_ms']} .. {cfg['end_ms']},"
        f" fence {cfg['fence_ts']}",
        "",
        "Cost-first pre-screen (research window, before the ladder):",
        "",
        "| construction | gross mean/d | gross Z | net mean/d | net Z |"
        " cost-first |",
        "|---|---|---|---|---|---|",
    ]
    for r in verdict["constructions"]:
        lines.append(
            f"| {r['name']} | {r['gross_mean']:.6f} | {r['gross_z']:.3f}"
            f" | {r['net_mean']:.6f} | {r['net_z']:.3f}"
            f" | {_b(r['cost_first_pass'])} |")
    lines += ["", "Ladder (only constructions that clear cost-first):", "",
              "| construction | screen mean/d | s1 | holdout MAR | holdout DD"
              " | s2 | research Sharpe/d | DSR | s3 | tail MAR | tail DD | s4 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in verdict["constructions"]:
        if not r["cost_first_pass"]:
            lines.append(f"| {r['name']} | — cost-dead, ladder skipped — |"
                         " | | | | | | | | | |")
            continue
        lines.append(
            f"| {r['name']} | {r['screen_mean']:.6f} | {_b(r['stage1_pass'])} "
            f"| {r['holdout_mar']:.3f} | {r['holdout_drawdown']:.3f}"
            f" | {_b(r['stage2_pass'])} | {r['research_sharpe']:.4f}"
            f" | {r['dsr'] if r['dsr'] is not None else '-'}"
            f" | {_b(r.get('stage3_pass'))} | {r['tail_mar']:.3f}"
            f" | {r['tail_drawdown']:.3f} | {_b(r['stage4_pass'])} |")
    lines += ["", "## Decision", "",
              "A construction is a survivor only if it clears the cost-first"
              " pre-screen and then every ladder stage; the verdict above is"
              " final (one-touch tail)."]
    return "\n".join(lines) + "\n"


def _b(v) -> str:
    return "-" if v is None else ("PASS" if v else "fail")


def cmd_run(out_dir: Path, cache_dir: str) -> None:
    reg_path = out_dir / "registration.json"
    if not reg_path.exists():
        sys.exit("no registration; run `python tools/resrev.py register` first"
                 " (the design must be frozen before any data look)")
    cfg = json.loads(reg_path.read_text())
    symbols = list_um_perp_symbols()
    print(f"{len(symbols)} archived USDT perps discovered")

    def fetch_daily(symbol, start, end):
        return fetch_daily_klines(symbol, start, end, cache_dir)

    def fetch_funding(symbol, start, end):
        return fetch_funding_rates(symbol, start, end, cache_dir)

    verdict = run_pipeline(cfg, symbols, fetch_daily, fetch_funding, out_dir)
    print(f"[{verdict['status']}] report: {out_dir / 'report.md'}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/resrev")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("register", help="freeze window, fence, and construction")
    run_p = sub.add_parser("run",
                           help="one-touch evaluation of the frozen design")
    run_p.add_argument("--cache-dir", default=".backtest_cache")
    args = p.parse_args()
    if args.command == "register":
        cmd_register(Path(args.out))
    else:
        cmd_run(Path(args.out), args.cache_dir)


if __name__ == "__main__":
    main()
