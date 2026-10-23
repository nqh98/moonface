#!/usr/bin/env python
"""eventtime one-touch run: calibrate dollar bars and compare paired exits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.eventtime.dollar_bars import (  # noqa: E402
    build_dollar_bars,
    calibrate_bar_size,
)
from moonface.research.eventtime.paired import (  # noqa: E402
    arm_metrics,
    paired_verdict,
    run_ladder,
)


def default_loaders(cfg: dict, cache_dir: str) -> dict:
    from moonface.research.eventtime.vision_klines import (  # noqa: E402
        fetch_vision_1m,
    )
    from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

    def calib_minutes():
        return fetch_vision_1m(
            cfg["symbol"],
            cfg["calib_start_ms"],
            cfg["calib_end_ms"],
            cache_dir,
        )

    def test_minutes():
        return fetch_vision_1m(
            cfg["symbol"],
            cfg["test_start_ms"],
            cfg["test_end_ms"],
            cache_dir,
        )

    def clock_4h():
        return fetch_perp_candles(
            cfg["symbol"],
            cfg["clock_timeframe"],
            cfg["test_start_ms"],
            cfg["test_end_ms"],
            cache_dir,
        )

    return {
        "calib_minutes": calib_minutes,
        "test_minutes": test_minutes,
        "clock_4h": clock_4h,
    }


def compute(cfg: dict, loaders: dict) -> dict:
    exit_rows = [(name, params) for name, params in cfg["exit_rows"]]
    calib_minutes = loaders["calib_minutes"]()
    test_minutes = loaders["test_minutes"]()
    clock_bars = loaders["clock_4h"]()

    bar_size = calibrate_bar_size(
        calib_minutes,
        cfg["calib_start_ms"],
        cfg["calib_end_ms"],
        window_min=cfg["bar_size_window_min"],
    )
    dollar_bars = build_dollar_bars(test_minutes, bar_size)
    entry_params = cfg["entry"]["params"]
    clock_rows = arm_metrics(clock_bars, entry_params, exit_rows=exit_rows)
    dollar_rows = arm_metrics(dollar_bars, entry_params, exit_rows=exit_rows)
    ladder = run_ladder(
        dollar_bars,
        entry_params,
        exit_rows=exit_rows,
        fence_fraction=cfg["fence_fraction"],
        fraction=cfg["fraction"],
        grid_size=cfg["grid_size"],
    )
    verdict = paired_verdict(
        clock_rows,
        dollar_rows,
        ladder,
        min_improve=cfg["min_improve"],
    )
    return {
        "bar_size": bar_size,
        "n_dollar_bars": len(dollar_bars),
        "n_clock_bars": len(clock_bars),
        "clock_rows": clock_rows,
        "dollar_rows": dollar_rows,
        "ladder": ladder,
        "verdict": verdict,
    }


def _result_md(cfg: dict, result: dict) -> str:
    verdict = result["verdict"]
    lines = [
        "# eventtime RESULT",
        "",
        f"- symbol: {cfg['symbol']}",
        f"- clock timeframe: {cfg['clock_timeframe']}",
        f"- calibrated bar size: {result['bar_size']:.4f}",
        f"- clock bars: {result['n_clock_bars']}",
        f"- dollar bars: {result['n_dollar_bars']}",
        "",
        "## Ladder",
        "",
        f"- ladder_pass: {result['ladder']['ladder_pass']}",
        f"- passing_exits: {', '.join(result['ladder']['passing_exits']) or 'none'}",
        f"- best_dsr: {result['ladder']['best_dsr']}",
        f"- best_tail_mar: {result['ladder']['best_tail_mar']}",
        "",
        "## Verdict",
        "",
        f"- best_improvement: {verdict['best_improvement']}",
        f"- improved_exits: {', '.join(verdict['improved_exits']) or 'none'}",
        f"- ladder_pass: {verdict['ladder_pass']}",
        f"- **VERDICT: {verdict['verdict'].upper()}**"
        + (f" ({verdict['reason']})" if verdict.get("reason") else ""),
    ]
    return "\n".join(lines) + "\n"


def cmd_run(out_dir: Path, cache_dir: str, loaders: dict | None = None) -> dict:
    reg_path = out_dir / "registration.json"
    if not reg_path.exists():
        sys.exit(f"{reg_path} missing; run --register first (and commit it)")
    results_path = out_dir / "results.json"
    if results_path.exists():
        sys.exit(f"{results_path} already exists; the run is one-touch")

    cfg = json.loads(reg_path.read_text())
    if loaders is None:
        loaders = default_loaders(cfg, cache_dir)

    result = compute(cfg, loaders)
    (out_dir / "RESULT.md").write_text(_result_md(cfg, result))
    results_path.write_text(json.dumps(result, indent=2))
    print(
        f"verdict: {result['verdict']['verdict']} "
        f"(improvement={result['verdict']['best_improvement']}, "
        f"ladder_pass={result['verdict']['ladder_pass']})"
    )
    return result
