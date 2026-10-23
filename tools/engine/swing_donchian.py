#!/usr/bin/env python3
"""Stage-3: run the Donchian walk-forward and render the honest verdict."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.kernel.econ import ECON_BAR, evaluate_econ
from moonface.research.trend_sim import TrendParams
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from moonface.kernel.walkforward import walk_forward


@dataclass(frozen=True)
class ResultInput:
    symbol: str
    interval: str
    passed: bool
    reasons: list[str]
    metrics: dict
    n_windows: int
    chosen_summary: str


def render_result(inp: ResultInput) -> str:
    verdict = "PASS (promote to paper — NOT live)" if inp.passed else "FAIL"
    m = inp.metrics
    caveat = ("Most likely outcome is no deployable edge; a FAIL is a valid, "
              "informative result and cheaper to learn now than with live capital.")
    return (
        f"# Donchian Walk-Forward Result — {inp.symbol} {inp.interval}\n\n"
        f"## Verdict: {verdict}\n\n"
        f"- windows (test-only): {inp.n_windows}\n"
        f"- {inp.chosen_summary}\n"
        f"- expectancy_r: {m.get('expectancy_r')}\n"
        f"- profit_factor: {m.get('profit_factor')} (floor {ECON_BAR.profit_factor})\n"
        f"- MAR: {m.get('mar')} (floor {ECON_BAR.mar_floor})\n"
        f"- max drawdown: {m.get('max_dd_r')}R (tol {ECON_BAR.max_dd_r}R @ f=0.01)\n"
        f"- robust fraction: {m.get('robust_frac')} (floor {ECON_BAR.robust_frac})\n\n"
        "## Reasons\n\n"
        + "\n".join(f"- {r}" for r in inp.reasons)
        + f"\n\n## Honest caveat\n\n{caveat}\n"
    )


_BASE = TrendParams(entry_n=20, trail_n=10, atr_period=14, k_stop=2.0,
                    long_only=True, fee_rate=0.00045, slippage=0.0005,
                    funding_enabled=True)
_GRID = [TrendParams(entry_n=en, trail_n=tn, atr_period=14, k_stop=2.0,
                     long_only=True, fee_rate=0.00045, slippage=0.0005,
                     funding_enabled=True)
         for en in (10, 20, 40) for tn in (10, 20)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Donchian walk-forward + verdict")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--cache-dir", default="cache/swing")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--out", default="experiments/deployable/DONCHIAN_WALKFORWARD_RESULT.md")
    args = ap.parse_args(argv)

    candles = fetch_perp_candles(args.symbol, args.interval, args.start_ms,
                                 args.end_ms, args.cache_dir)
    funding = fetch_funding_rates(args.symbol, args.start_ms, args.end_ms, args.cache_dir)

    step = {"4h": 2190, "1d": 365}[args.interval]
    train = step * 2
    res = walk_forward(candles, funding, _GRID, train_bars=train,
                       test_bars=step, step_bars=step, base_params=_BASE)
    verdict = evaluate_econ(res.test_summaries, res.aggregated)
    mode = Counter((p.entry_n, p.trail_n) for p in res.chosen_params).most_common(1)[0][0]
    inp = ResultInput(
        symbol=args.symbol, interval=args.interval,
        passed=verdict.passed, reasons=list(verdict.reasons),
        metrics=dict(verdict.metrics), n_windows=len(res.test_summaries),
        chosen_summary=f"entry_n/trail_n mode = {mode[0]}/{mode[1]}",
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_result(inp))
    print(f"verdict: {'PASS' if inp.passed else 'FAIL'} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
