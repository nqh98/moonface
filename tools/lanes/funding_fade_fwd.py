#!/usr/bin/env python
# tools/funding_fade_fwd.py
"""funding_fade_fwd draft-preparation CLI. Subcommands:

  dryrun      reproduce the archived positioning_exits row on pre-cutoff data
  analyze     DD-budget candidates + verdict-trigger power calc from streams
  null-guard  100-seed funding-shuffle guard (must FAIL >= 95 of 100)
  identity    print the identity_hash for a (budget, N, months) choice

No subcommand can observe post-cutoff data: every load path goes through
funding_fade_fwd.load_pre_cutoff, which hard-clamps at CUTOFF_MS.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research import funding_fade_fwd as fwd
from moonface.research.fwd_analysis import (bootstrap_expectancy_ci,
                                            cumulative_min, forward_success,
                                            max_drawdown_path, null_p95_threshold,
                                            required_n, ruin_probability,
                                            stream_sigma,
                                            time_under_water_days,
                                            trades_per_year)
from moonface.kernel.fwd_null import shuffle_funding_segments

DEFAULT_OUT = Path("experiments/funding_fade_fwd")
DEFAULT_BUDGETS = [-40.0, -50.0, -64.0]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_dryrun(cache_dir: str, out_root: Path, loader=None) -> int:
    load = loader or fwd.load_pre_cutoff
    perp, funding = load(cache_dir)
    streams = fwd.regenerate(perp, funding)
    ok, got = fwd.reproduction_report(streams)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "streams.json").write_text(json.dumps(
        {"research": [[ts, r] for ts, r in streams.research],
         "tail": [[ts, r] for ts, r in streams.tail]}), encoding="utf-8")
    (out_root / "dryrun_report.json").write_text(json.dumps(
        {"generated": _now(), "archived": fwd.ARCHIVED,
         "baseline_amendment1": fwd.BASELINE, "regenerated": got,
         "reproduced": ok}, indent=2, sort_keys=True), encoding="utf-8")
    if ok:
        print("DRY-RUN REPRODUCED: all completed-candle baseline figures "
              "match exactly (Amendment 1).")
        return 0
    print("DRY-RUN MISMATCH — STOP AND ASK (spec 5.2). No silent patching.")
    for k, v in fwd.BASELINE.items():
        if got[k] != v:
            print(f"  {k}: archived={v} regenerated={got[k]}")
    return 1


def _load_streams(out_root: Path) -> tuple[list, list]:
    data = json.loads((out_root / "streams.json").read_text(encoding="utf-8"))
    research = [(int(ts), float(r)) for ts, r in data["research"]]
    tail = [(int(ts), float(r)) for ts, r in data["tail"]]
    return research, tail


def cmd_analyze(out_root: Path, budgets: list[float], months: int,
                resamples: int = 10_000) -> int:
    research, tail = _load_streams(out_root)
    full = research + tail
    rs_full = [r for _, r in full]
    rs_research = [r for _, r in research]
    rs_tail = [r for _, r in tail]
    rate = trades_per_year(full)
    horizon = max(1, round(rate * months / 12.0))
    mu = sum(rs_research) / len(rs_research)
    sigma = stream_sigma(rs_research)
    rows = []
    for budget in budgets:
        rows.append({
            "budget_r": budget,
            "capital_at_risk_pct": round(abs(budget) * fwd.FRACTION * 100, 2),
            "p_ruin_measured": ruin_probability(rs_full, budget, horizon,
                                                resamples=resamples),
            "p_ruin_zero_edge": ruin_probability(rs_full, budget, horizon,
                                                 resamples=resamples,
                                                 demean=True),
            "p_ruin_measured_peak_relative": ruin_probability(
                rs_full, budget, horizon, resamples=resamples,
                peak_relative=True),
        })
    analysis = {
        "generated": _now(),
        "inputs": {"research_n": len(rs_research), "tail_n": len(rs_tail),
                   "research_mu": round(mu, 4), "research_sigma":
                   round(sigma, 4), "trades_per_year": round(rate, 2),
                   "horizon_trades": horizon, "months": months},
        "history": {
            "full_cumulative_min_r": round(cumulative_min(rs_full), 4),
            "full_max_dd_r": round(max_drawdown_path(rs_full), 4),
            "research_max_dd_r": round(max_drawdown_path(rs_research), 4),
            "time_under_water_days": round(time_under_water_days(full), 1),
        },
        "expectancy_ci": {
            "research_95": bootstrap_expectancy_ci(rs_research,
                                                   resamples=resamples),
            "tail_95": bootstrap_expectancy_ci(rs_tail, resamples=resamples),
        },
        "budgets": rows,
        "trigger": {
            "required_n_power50": required_n(mu, sigma, power=0.5),
            "required_n_power80": required_n(mu, sigma, power=0.8),
            "calendar_months": months,
        },
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    (out_root / "analysis.md").write_text(_render_analysis(analysis),
                                          encoding="utf-8")
    print(f"analysis written to {out_root}/analysis.{{json,md}}")
    return 0


def _render_analysis(a: dict) -> str:
    i, h, t = a["inputs"], a["history"], a["trigger"]
    lines = [
        "# funding_fade_fwd — pre-cutoff analysis (drafting input)", "",
        f"- generated: {a['generated']}",
        f"- research n={i['research_n']} mu={i['research_mu']}R "
        f"sigma={i['research_sigma']}R; tail n={i['tail_n']}",
        f"- trades/year {i['trades_per_year']}; "
        f"{i['months']}-month horizon = {i['horizon_trades']} trades",
        f"- history: cum-min {h['full_cumulative_min_r']}R, "
        f"max peak-DD {h['full_max_dd_r']}R "
        f"(research-only {h['research_max_dd_r']}R), "
        f"longest TUW {h['time_under_water_days']}d",
        f"- expectancy 95% CI: research {a['expectancy_ci']['research_95']}, "
        f"tail {a['expectancy_ci']['tail_95']}", "",
        "| budget R | capital at risk (f=0.01) | P(ruin, measured) | "
        "P(ruin, zero-edge) | P(ruin, peak-rel) |",
        "|---|---|---|---|---|",
    ]
    for b in a["budgets"]:
        lines.append(
            f"| {b['budget_r']} | {b['capital_at_risk_pct']}% | "
            f"{b['p_ruin_measured']:.4f} | {b['p_ruin_zero_edge']:.4f} | "
            f"{b['p_ruin_measured_peak_relative']:.4f} |")
    lines += [
        "",
        f"Verdict-trigger N (95% CI excludes 0): power 0.5 -> "
        f"{t['required_n_power50']} trades; power 0.8 -> "
        f"{t['required_n_power80']} trades; calendar floor "
        f"{t['calendar_months']} months. Later-of semantics; the human "
        "chooses the power level and budget at sign-off.",
    ]
    return "\n".join(lines) + "\n"


def cmd_null_guard(cache_dir: str, out_root: Path, runs: int = 200,
                   loader=None) -> int:
    """Two-phase guard (Amendment 2): phase 1 collects every null's tail
    stream; phase 2 evaluates the full three-condition forward rule against
    the null p95 computed over the same set. The <=5% null pass rate holds
    by construction (circularity acknowledged in AMENDMENTS.md) — this run
    validates machinery, not the criterion."""
    load = loader or fwd.load_pre_cutoff
    perp, funding = load(cache_dir)
    tails: list[list[float]] = []
    for seed in range(runs):
        null_funding = shuffle_funding_segments(funding, seed)
        streams = fwd.regenerate(perp, null_funding)
        tails.append([r for _, r in streams.tail])
    nets = [sum(rs) for rs in tails]
    threshold = null_p95_threshold(nets)
    n_pass = sum(1 for rs in tails if forward_success(rs, threshold))
    guard_ok = (runs - n_pass) / runs >= 0.95
    nets_sorted = sorted(nets)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "null_guard.json").write_text(json.dumps(
        {"generated": _now(), "runs": runs, "seeds": f"0..{runs - 1}",
         "null_p95_threshold": round(threshold, 4),
         "null_net_r": {"min": round(nets_sorted[0], 4),
                        "median": round(nets_sorted[runs // 2], 4),
                        "max": round(nets_sorted[-1], 4)},
         "null_passes": n_pass, "fail_fraction": (runs - n_pass) / runs,
         "guard_ok": guard_ok,
         "criterion": "forward_success (Amendment 2, all three conditions) "
                      "on OOS-tail stream",
         "circularity_note": "condition (iii) caps null passes by "
                             "construction; run validates machinery only"},
        indent=2, sort_keys=True), encoding="utf-8")
    print(f"null guard: {runs - n_pass}/{runs} nulls FAIL forward_success "
          f"(null p95 = {threshold:.4f}R) -> guard_ok={guard_ok}")
    return 0 if guard_ok else 1


def cmd_identity(dd_budget_r: float, n_trades: int, months: int) -> int:
    print(fwd.identity_hash(dd_budget_r, n_trades, months))
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="funding_fade_fwd draft prep")
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-root", default=str(DEFAULT_OUT))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dryrun")
    a = sub.add_parser("analyze")
    a.add_argument("--budgets", type=float, nargs="+", default=DEFAULT_BUDGETS)
    a.add_argument("--months", type=int, default=12)
    a.add_argument("--resamples", type=int, default=10_000)
    g = sub.add_parser("null-guard")
    g.add_argument("--runs", type=int, default=200)
    ident = sub.add_parser("identity")
    ident.add_argument("--dd-budget-r", type=float, required=True)
    ident.add_argument("--n-trades", type=int, required=True)
    ident.add_argument("--months", type=int, default=12)
    args = p.parse_args()
    out_root = Path(args.out_root)
    if args.cmd == "dryrun":
        sys.exit(cmd_dryrun(args.cache_dir, out_root))
    if args.cmd == "analyze":
        sys.exit(cmd_analyze(out_root, args.budgets, args.months,
                             args.resamples))
    if args.cmd == "null-guard":
        sys.exit(cmd_null_guard(args.cache_dir, out_root, args.runs))
    if args.cmd == "identity":
        sys.exit(cmd_identity(args.dd_budget_r, args.n_trades, args.months))


if __name__ == "__main__":
    main()
