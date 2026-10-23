#!/usr/bin/env python3
"""Slice-2 (robustness-only): re-evaluate the Donchian robustness gate over a
denser, overlapping set of full-length deployment windows.

Strategy, params, Donchian construction, engine, and every economic gate are
UNCHANGED from Slice-1 — the runner imports the exact `_BASE`/`_GRID` objects
from `swing_donchian`, so strategy identity is guaranteed at the object level.
The ONLY lever is the walk-forward step:

- the four aggregate gates (PF/expectancy/MAR/maxDD) come from the original
  non-overlapping yearly run (`step = 1 year`) so the pooled R is uncorrupted;
- `robust_frac` is recomputed over overlapping 1-year windows advanced one
  quarter at a time (`step = 1 quarter`), via the unchanged `evaluate_econ`.

See experiments/deployable/SLICE2_DESIGN.md (frozen pre-registration).
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.kernel.econ import ECON_BAR, evaluate_econ, EconVerdict
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from moonface.kernel.walkforward import WalkResult, walk_forward
from tools.engine.swing_donchian import _BASE, _GRID

# year length in bars per interval (mirrors swing_donchian.step)
_YEAR_BARS = {"4h": 2190, "1d": 365}


def run_slice2(candles, funding_points, year_step: int) -> tuple[WalkResult, WalkResult, EconVerdict]:
    """Two walk-forwards over the same data/strategy: a non-overlapping yearly
    run for the aggregate gates and a quarterly-overlapping run for robustness.
    The verdict reads aggregate gates from the clean run and robust_frac from
    the dense run."""
    quarter_step = max(1, year_step // 4)
    train = year_step * 2
    res_clean = walk_forward(candles, funding_points, _GRID, train_bars=train,
                             test_bars=year_step, step_bars=year_step, base_params=_BASE)
    res_dense = walk_forward(candles, funding_points, _GRID, train_bars=train,
                             test_bars=year_step, step_bars=quarter_step, base_params=_BASE)
    verdict = evaluate_econ(res_dense.test_summaries, res_clean.aggregated)
    return res_clean, res_dense, verdict


def render_slice2(symbol: str, interval: str, verdict: EconVerdict,
                  clean_windows: int, dense_windows: int) -> str:
    head = "PASS (promote to paper — NOT live)" if verdict.passed else "FAIL"
    m = verdict.metrics
    caveat = ("Overlapping windows are autocorrelated (consecutive 1-year windows "
              "share ~3/4 of their data), so robust_frac here is a smoother estimate "
              "of the same quantity, not independent trials. A FAIL remains a valid, "
              "informative result and cheaper to learn now than with live capital.")
    return (
        f"# Donchian Walk-Forward Result — Slice-2 (robustness-only) — {symbol} {interval}\n\n"
        f"## Verdict: {head}\n\n"
        f"- aggregate gates from non-overlapping yearly run: {clean_windows} windows\n"
        f"- robustness from overlapping 1-year windows (quarterly step): {dense_windows} windows\n"
        f"- expectancy_r: {m.get('expectancy_r')}\n"
        f"- profit_factor: {m.get('profit_factor')} (floor {ECON_BAR.profit_factor})\n"
        f"- MAR: {m.get('mar')} (floor {ECON_BAR.mar_floor})\n"
        f"- max drawdown: {m.get('max_dd_r')}R (tol {ECON_BAR.max_dd_r}R @ f=0.01)\n"
        f"- robust fraction: {m.get('robust_frac')} (floor {ECON_BAR.robust_frac})\n\n"
        "## Reasons\n\n"
        + "\n".join(f"- {r}" for r in verdict.reasons)
        + f"\n\n## Honest caveat\n\n{caveat}\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Donchian walk-forward Slice-2 (robustness-only)")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="4h", choices=["4h", "1d"])
    ap.add_argument("--cache-dir", default="cache/swing")
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--out", default="experiments/deployable/DONCHIAN_SLICE2_RESULT.md")
    args = ap.parse_args(argv)

    candles = fetch_perp_candles(args.symbol, args.interval, args.start_ms,
                                 args.end_ms, args.cache_dir)
    funding = fetch_funding_rates(args.symbol, args.start_ms, args.end_ms, args.cache_dir)

    year_step = _YEAR_BARS[args.interval]
    res_clean, res_dense, verdict = run_slice2(candles, funding, year_step)
    mode = Counter((p.entry_n, p.trail_n) for p in res_clean.chosen_params).most_common(1)[0][0]
    md = render_slice2(args.symbol, args.interval, verdict,
                       clean_windows=len(res_clean.test_summaries),
                       dense_windows=len(res_dense.test_summaries))
    md += f"\n## Chosen params (clean-run mode)\n\n- entry_n/trail_n mode = {mode[0]}/{mode[1]}\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"verdict: {'PASS' if verdict.passed else 'FAIL'} "
          f"(clean={len(res_clean.test_summaries)}w dense={len(res_dense.test_summaries)}w) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
