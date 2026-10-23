#!/usr/bin/env python3
"""tools/portfolio_search.py -- staged portfolio-tournament CLI (mirror practical_search).

Staged so the Explore/Select/Validate split is enforced structurally:
  --register : freeze PREREGISTRATION.md (grid/splits/gates) -- commit before --explore.
  --explore  : stage 1: fetch 1h+4h, build component positions, basket screen,
               run_explore on train+oos -> explore_leaderboard.json.
  --select   : stage 2: re-run explore then select -> frozen_candidates.json
               -- commit before --validate.
  --validate : stage 3+4: walk-forward econ on train+oos + sealed last-20%
               -> RESULT.md + result.json.

Free Binance BTCUSDT OHLCV only. PAPER ONLY."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.portfolio.components import center_components, TIMEFRAMES  # noqa: E402
from moonface.research.portfolio.grid import FROZEN_PORTFOLIOS, N_TRIALS  # noqa: E402
from moonface.research.portfolio.pipeline import (  # noqa: E402
    run_explore, select, validate_all, freeze_candidates, to_leaderboard,
    render_result, build_portfolio_positions,
)
from moonface.research.portfolio.streams import component_positions, asset_bar_r, position_returns  # noqa: E402
from moonface.research.portfolio.correlation import step0_screen  # noqa: E402
from moonface.research.portfolio.evaluate import summarize_portfolio  # noqa: E402

PORTFOLIO_MIN_BARS = 1000
# ~6.5y window (BTCUSDT perp has 1h data from 2020-01). Re-registered from the
# BUILD_STATUS 3y default (1687305600000) before any run/seal — a clean fresh
# registration, not a post-hoc change.
START_MS = 1577836800000  # 2020-01-01 00:00 UTC
END_MS = 1782000000000


def _sha(candles) -> str:
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _split_60_20_20(candles):
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    return candles[:a], candles[a:b], candles[b:]


def _feasible(by_tf: dict) -> str | None:
    for tf, candles in by_tf.items():
        if len(candles) < PORTFOLIO_MIN_BARS:
            return f"FEASIBILITY FAIL: {tf} has {len(candles)} < {PORTFOLIO_MIN_BARS}"
    return None


def _load(cache_dir: str, symbol: str) -> dict:
    from moonface.research.universe_data import fetch_perp_candles  # noqa: E402
    return {tf: fetch_perp_candles(symbol, tf, START_MS, END_MS, cache_dir)
            for tf in TIMEFRAMES}


def _write_prereg(out: Path, data_shas: dict) -> None:
    comps = center_components()
    lines = [
        "# Portfolio Tournament PREREGISTRATION (frozen)", "",
        f"- asof: {datetime.now(timezone.utc).isoformat()}",
        f"- window: {START_MS}..{END_MS}",
        f"- timeframes: {', '.join(TIMEFRAMES)}",
        f"- n_trials (pooled): {N_TRIALS}",
        "- split: chronological Train-OOS / Validate / Sealed 60/20/20 per timeframe",
        "", "## Components (frozen system_cells centers)", "",
    ]
    for c in comps:
        lines.append(f"- {c.label} family={c.family} exit={c.exit_name} "
                      f"tf={c.timeframe} h={c.h}")
    lines += ["", "## Operator grid (frozen)", ""]
    for label, op, kw in FROZEN_PORTFOLIOS:
        lines.append(f"- {label}: {op} {kw}")
    lines += [
        "", "## Per-timeframe data fingerprint", "",
        "| timeframe | bars | data_sha |", "|---|---|---|",
    ]
    for tf in TIMEFRAMES:
        sha = data_shas.get(tf, "-")
        # bars count stored alongside sha during explore; here write sha only
        lines.append(f"| {tf} | pending | {sha} |")
    out.write_text("\n".join(lines) + "\n")


def _build_positions_and_bar_r(
    by_tf: dict, train_oos_by_tf: dict,
) -> tuple[list[list[float]], list[float], list]:
    """Build grid-aligned component positions and asset_bar_r on 1h train+oos slice.

    Returns (positions_by_comp, asset_bar_r_series, grid_candles_train_oos).
    """
    comps = center_components()
    grid_candles = train_oos_by_tf["1h"]
    bar_r = asset_bar_r(grid_candles)
    positions_by_comp: list[list[float]] = []
    for cell in comps:
        aligned = component_positions(by_tf, cell, grid_candles)
        # Trim to grid_candles length (should match, but guard)
        positions_by_comp.append(aligned[:len(grid_candles)])
    return positions_by_comp, bar_r, grid_candles


def _split_all(by_tf: dict) -> tuple[dict, dict, dict]:
    """60/20/20 split per timeframe -> (train_oos_by_tf, validate_by_tf, sealed_by_tf)."""
    train_oos: dict = {}
    validate: dict = {}
    sealed: dict = {}
    for tf, candles in by_tf.items():
        t, v, s = _split_60_20_20(candles)
        train_oos[tf] = t
        validate[tf] = v
        sealed[tf] = s
    return train_oos, validate, sealed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="BTC portfolio tournament (1h+4h staged CLI)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--explore", action="store_true")
    mode.add_argument("--select", action="store_true")
    mode.add_argument("--validate", action="store_true")
    ap.add_argument("--symbol", default="BTCUSDT")
    # Vestigial: every mode uses the frozen module constants START_MS..END_MS
    # (see top of file), so --start-ms/--end-ms are accepted but never read.
    # Kept optional for backward-compatible callers; safe to remove outright.
    ap.add_argument("--start-ms", type=int, required=False, default=None)
    ap.add_argument("--end-ms", type=int, required=False, default=None)
    ap.add_argument("--cache-dir", default=".backtest_cache")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # --register: writes prereg (offline-safe, no data needed)
    if args.register:
        data_shas = {tf: f"sha:{tf}:pending" for tf in TIMEFRAMES}
        _write_prereg(out / "PREREGISTRATION.md", data_shas)
        print(f"registered -> {out}/PREREGISTRATION.md (commit before --explore)")
        return 0

    # --validate without frozen_candidates -> exit 3 (BEFORE loading data)
    frozen_path = out / "frozen_candidates.json"
    if args.validate and not frozen_path.exists():
        print(f"no frozen_candidates.json in {out}; run --select first")
        return 3

    # All other modes need data
    by_tf = _load(args.cache_dir, args.symbol)
    fail = _feasible(by_tf)
    if fail:
        print(fail)
        return 2

    # Compute data SHAs and update prereg with real values
    shas = {tf: _sha(by_tf[tf]) for tf in TIMEFRAMES}

    # --explore: build positions, screen basket, run_explore -> leaderboard
    if args.explore:
        train_oos_by_tf, _, _ = _split_all(by_tf)
        positions_by_comp, bar_r, grid_candles = (
            _build_positions_and_bar_r(by_tf, train_oos_by_tf)
        )
        # Component-level returns for correlation screening
        comps = center_components()
        comp_returns_list = [
            position_returns(positions_by_comp[i], bar_r, grid_candles)
            for i in range(len(comps))
        ]
        # Step-0 correlation screen
        screen = step0_screen(comps, comp_returns_list)
        print(f"correlation screen: basket_size={screen['basket_size']} "
              f"verdict={screen['verdict']}")
        if screen["verdict"] == "thesis_dead":
            print("CORRELATION SCREEN: thesis_dead (basket < min_size)")
        # Component-level metrics for later battery use
        comp_metrics_list = [summarize_portfolio(cr) for cr in comp_returns_list]
        rows = run_explore(positions_by_comp, bar_r, grid_candles)
        # Enrich with screen + component metrics
        for r in rows:
            r["screen"] = screen
        (out / "explore_leaderboard.json").write_text(
            json.dumps(rows, indent=2, default=str))
        print(f"explored {len(rows)} portfolios -> {out}/explore_leaderboard.json")
        return 0

    # --select: re-run explore then apply selection battery
    if args.select:
        train_oos_by_tf, _, _ = _split_all(by_tf)
        positions_by_comp, bar_r, grid_candles = (
            _build_positions_and_bar_r(by_tf, train_oos_by_tf)
        )
        comps = center_components()
        comp_returns_list = [
            position_returns(positions_by_comp[i], bar_r, grid_candles)
            for i in range(len(comps))
        ]
        comp_metrics_list = [summarize_portfolio(cr) for cr in comp_returns_list]
        explore_rows = run_explore(positions_by_comp, bar_r, grid_candles)
        survivors = select(
            explore_rows, positions_by_comp, bar_r, grid_candles,
            comp_metrics_list,
        )
        frozen = freeze_candidates(survivors)
        (out / "frozen_candidates.json").write_text(
            json.dumps(frozen, indent=2, default=str))
        print(f"selected {len(frozen)} survivors -> {out}/frozen_candidates.json "
              f"(commit before --validate)")
        return 0

    # --validate: walk-forward + sealed holdout
    frozen = json.loads(frozen_path.read_text())
    train_oos_by_tf, _, sealed_by_tf = _split_all(by_tf)

    # Rebuild positions on full train+oos for operator-level returns
    positions_by_comp, bar_r, grid_candles = (
        _build_positions_and_bar_r(by_tf, train_oos_by_tf)
    )
    comps = center_components()
    comp_returns_list = [
        position_returns(positions_by_comp[i], bar_r, grid_candles)
        for i in range(len(comps))
    ]
    comp_metrics_list = [summarize_portfolio(cr) for cr in comp_returns_list]

    # Build sealed component positions/bar_r/grid once (same for all portfolios)
    sealed_positions_by_comp, sealed_bar_r, sealed_grid = (
        _build_positions_and_bar_r({tf: sealed_by_tf[tf] for tf in by_tf}, sealed_by_tf)
    )

    # Build per-label train+oos returns and sealed returns for each survivor
    n_1h = len(train_oos_by_tf["1h"])
    n_sealed_1h = len(sealed_by_tf["1h"])
    train_oos_by_label: dict[str, list[float]] = {}
    sealed_by_label: dict[str, list[float]] = {}
    for r in frozen:
        label = r["label"]
        # Reconstruct operator positions from the grid on train+oos
        pos = None
        for fp in FROZEN_PORTFOLIOS:
            if fp[0] == label:
                pos = build_portfolio_positions(
                    fp, positions_by_comp, bar_r, grid_candles)
                break
        if pos is None:
            pos = [0.0] * n_1h
        train_oos_by_label[label] = position_returns(
            pos, bar_r, grid_candles)
        # Sealed segment positions
        sealed_positions = [0.0] * n_sealed_1h
        if pos and n_sealed_1h > 0:
            for fp in FROZEN_PORTFOLIOS:
                if fp[0] == label:
                    sealed_positions = build_portfolio_positions(
                        fp, sealed_positions_by_comp, sealed_bar_r, sealed_grid)
                    break
        sealed_by_label[label] = position_returns(
            sealed_positions, sealed_bar_r if n_sealed_1h > 0 else [],
            sealed_grid if n_sealed_1h > 0 else [])

    # Walk-forward parameters
    test_bars = max(200, n_1h // 5)
    step_bars = max(50, test_bars // 4)
    result_rows = validate_all(
        frozen, train_oos_by_label, sealed_by_label,
        test_bars, step_bars, comp_metrics_list,
    )
    asof = datetime.now(timezone.utc).isoformat()
    (out / "RESULT.md").write_text(render_result(result_rows, asof, shas))
    (out / "result.json").write_text(
        json.dumps(to_leaderboard(result_rows), indent=2, default=str))
    accept = any(r.get("verdict") == "candidate" for r in result_rows)
    print(f"verdict: {'CANDIDATE(S)' if accept else 'NEGATIVE'} -> {out}/RESULT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
