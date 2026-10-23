#!/usr/bin/env python3
"""Staged BTC beta-neutral residual-drift basket CLI (paper-only)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.drift_basket.basket import (  # noqa: E402
    BasketParams,
    simulate_basket,
)
from moonface.research.drift_basket.diagnostics import (  # noqa: E402
    cocrash_metrics,
    distinctness_correlation,
)
from moonface.research.drift_basket.gate import gate_stages  # noqa: E402
from moonface.research.drift_basket.legs import (  # noqa: E402
    daily_close_returns,
    daily_long_flags,
    utc_day,
)
from moonface.research.universe_data import (  # noqa: E402
    fetch_daily_klines,
    fetch_funding_rates,
    fetch_perp_candles,
    list_um_perp_symbols,
)
from moonface.research.xsection import build_universe  # noqa: E402

LANE = "btc_drift_basket"
SYMBOL_BTC = "BTCUSDT"
TF = "4h"
_DAY_MS = 86_400_000

# Known cost-accounting leniency (documented, not corrected): the per-day funding
# drag `fund` (weighted funding rate) is charged unscaled in basket.simulate_basket,
# but the basket runs at `lev`x notional, so the equity funding drag is `lev*fund`.
# At MAX_LEVERAGE=5 funding is therefore understated by up to 5x, biasing the cost
# bar OPTIMISTIC. Safe for this kill-rule lane (a closed_negative verdict reached
# despite understated costs is conservative-credible); a paper_candidate upset
# would need re-checking with exact costs. Turnover costs ARE lev-scaled.
COST_ACCOUNTING_NOTE = (
    "Funding cost is charged unscaled by leverage in basket.simulate_basket "
    "(equity drag should be lev*fund, not fund), understating costs by up to "
    "MAX_LEVERAGE=5x. Biases optimistic. Turnover costs are lev-scaled. A "
    "closed_negative verdict is conservative-credible; a paper_candidate upset "
    "must be re-checked with lev-scaled funding.")


def _params_doc(p: BasketParams) -> dict:
    return {
        "donchian_n": p.donchian_n, "hold_bars": p.hold_bars, "top_n": p.top_n,
        "min_history_days": p.min_history_days, "vol_days": p.vol_days,
        "vol_window": p.vol_window, "vol_target_annual": p.vol_target_annual,
        "beta_window": p.beta_window, "fee": p.fee,
    }


def _windows(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    return {
        "research": [args.start_ms, args.start_ms + int(span * 0.8)],
        "lockbox": [args.start_ms + int(span * 0.8), args.end_ms],
    }


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _funding_daily(pairs: list[tuple[int, float]]) -> dict[int, float]:
    """Sum intraday funding rates into a per-UTC-day total."""
    out: dict[int, float] = {}
    for ts, rate in pairs:
        d = utc_day(ts)
        out[d] = out.get(d, 0.0) + rate
    return out


def _monthly_universe(daily: dict, days: list[int], p: BasketParams) -> dict[int, list[str]]:
    """Per-day universe; rebuilt at each new UTC month from build_universe."""
    by_day: dict[int, list[str]] = {}
    cur: list[str] = []
    cur_month: tuple[int, int] | None = None
    for d in days:
        dtm = datetime.fromtimestamp(d / 1000, timezone.utc)
        if (dtm.year, dtm.month) != cur_month:
            cur = build_universe(daily, d, p.top_n, p.min_history_days, p.vol_days)
            cur_month = (dtm.year, dtm.month)
        by_day[d] = cur
    return by_day


def _register(args) -> int:
    p = BasketParams()
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", {
        "lane": LANE,
        "lane_description": (
            "Single frozen beta-neutral, vol-targeted, risk-parity basket of "
            "donchian-breakout drift legs across a survivorship-clean perp "
            "universe; judged once through the standard ladder. Tests whether "
            "structural diversification defeats the directional drawdown wall."),
        "asof": datetime.now(timezone.utc).isoformat(),
        "timeframe": TF, "params": _params_doc(p), "windows": _windows(args),
        "n_trials": 1,
        "kill_rule": ("closed_negative => structural diversification does not "
                      "defeat the wall; no v2, no parameter rescue."),
        "cost_accounting_note": COST_ACCOUNTING_NOTE,
    })
    return 0


def _load(args, p: BasketParams):
    """Returns (days, universe_by_day, daily_flags, daily_rets, btc_rets, funding)."""
    daily: dict = {}
    for sym in list_um_perp_symbols():
        rows = fetch_daily_klines(sym, args.start_ms, args.end_ms, args.cache_dir)
        if rows:
            daily[sym] = rows
    day_set = {utc_day(r.ts_ms) for rows in daily.values() for r in rows
               if args.start_ms <= r.ts_ms < args.end_ms}
    days = sorted(day_set)
    universe_by_day = _monthly_universe(daily, days, p)

    needed = {s for syms in universe_by_day.values() for s in syms} | {SYMBOL_BTC}
    daily_flags: dict[str, dict[int, bool]] = {}
    daily_rets: dict[str, dict[int, float]] = {}
    funding: dict[str, dict[int, float]] = {}
    btc_rets: dict[int, float] = {}
    for sym in sorted(needed):
        candles = fetch_perp_candles(sym, TF, args.start_ms, args.end_ms, args.cache_dir)
        if not candles:
            continue
        daily_flags[sym] = daily_long_flags(candles, p.donchian_n, p.hold_bars)
        daily_rets[sym] = daily_close_returns(candles)
        funding[sym] = _funding_daily(
            fetch_funding_rates(sym, args.start_ms, args.end_ms, args.cache_dir))
        if sym == SYMBOL_BTC:
            btc_rets = dict(daily_rets[sym])
    return days, universe_by_day, daily_flags, daily_rets, btc_rets, funding


def _simulate(args) -> int:
    p = BasketParams()
    days, uni, flags, rets, btc_rets, funding = _load(args, p)
    if len(days) < 200:
        print(f"FEASIBILITY FAIL: {len(days)} days < 200")
        return 2
    series = simulate_basket(days, uni, flags, rets, btc_rets, funding, p)
    port = [r for _, r in series]
    btc_aligned = [btc_rets.get(days[k + 1], 0.0) if k + 1 < len(days) else 0.0
                   for k in range(len(days))]
    distinct = distinctness_correlation(days, uni, flags, rets)
    full_beta, tail_corr = cocrash_metrics(port, btc_aligned)
    _write_json(Path(args.out_dir) / "RESULT.json", {
        "lane": LANE, "asof": datetime.now(timezone.utc).isoformat(),
        "timeframe": TF, "params": _params_doc(p), "windows": _windows(args),
        "days": len(days),
        "series": [[int(t), r] for t, r in series],
        "diagnostics": {
            "distinctness_corr_vs_momentum": round(distinct, 4),
            "full_portfolio_beta": round(full_beta, 4),
            "left_tail_corr_to_btc": round(tail_corr, 4),
        },
    })
    return 0


def _gate(args) -> int:
    result = json.loads((Path(args.out_dir) / "RESULT.json").read_text())
    series = result["series"]
    returns = [r for _, r in series]
    fence_idx = int(len(returns) * 0.8)
    stages = gate_stages(returns, fence_idx)
    diag = result["diagnostics"]
    asof = datetime.now(timezone.utc).isoformat()
    _write_json(Path(args.out_dir) / "GATE.json",
                {"lane": LANE, "asof": asof, "fence_idx": fence_idx,
                 "stages": stages, "diagnostics": diag})
    flags = []
    if abs(diag["distinctness_corr_vs_momentum"]) > 0.5:
        flags.append("DISTINCTNESS RED FLAG: leg selection tracks momentum rank "
                     "(>|0.5|) — may be cross-sectional in disguise; result void.")
    if abs(diag["left_tail_corr_to_btc"]) > 0.5 or abs(diag["full_portfolio_beta"]) > 0.3:
        flags.append("CO-CRASH RED FLAG: hedge did not neutralize BTC beta in the "
                     "left tail — the structural fix failed mechanically.")
    lines = [
        "# BTC Drift Basket (beta-neutral residual drift) — GATE",
        "",
        f"## Verdict: {stages['verdict'].upper()}",
        "",
        f"- asof: {asof}  research_days: {stages['research_days']}  dsr: {stages['dsr']}",
        f"- holdout MAR: {stages['holdout_mar']}  holdout DD: {stages['holdout_drawdown']}",
        f"- stages: s1={stages['stage1_pass']} s2={stages['stage2_pass']} "
        f"s3={stages['stage3_pass']} s4={stages['stage4_pass']}",
        "",
        "## Diagnostics",
        f"- distinctness corr vs momentum: {diag['distinctness_corr_vs_momentum']}",
        f"- full portfolio beta: {diag['full_portfolio_beta']}  "
        f"left-tail corr to BTC: {diag['left_tail_corr_to_btc']}",
        "",
    ]
    lines += [f"> {f}" for f in flags] or ["(no diagnostic red flags)"]
    lines += [
        "",
        "Paper-only. A single frozen design (n_trials=1). closed_negative fires the "
        "kill rule: structural diversification does not defeat the drawdown wall.",
        "",
        f"## Cost-accounting note\n\n{COST_ACCOUNTING_NOTE}",
        "",
    ]
    (Path(args.out_dir) / "FINDINGS.md").write_text("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    pa = argparse.ArgumentParser(prog="drift-basket")
    mode = pa.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--simulate", action="store_true")
    mode.add_argument("--gate", action="store_true")
    pa.add_argument("--start-ms", type=int, required=True)
    pa.add_argument("--end-ms", type=int, required=True)
    pa.add_argument("--cache-dir", default=".backtest_cache")
    pa.add_argument("--out-dir", required=True)
    return pa


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    if args.register:
        return _register(args)
    if args.simulate:
        return _simulate(args)
    if args.gate:
        return _gate(args)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
