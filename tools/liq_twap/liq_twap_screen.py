#!/usr/bin/env python
"""Lane 1 Track-A CLI: run the frozen liquidation-TWAP proxy pre-screen."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from moonface.data.bundle import load_bundle
from moonface.research.liq_twap.runner import (
    BTC_ASSET,
    START_MS,
    render_verdict,
    run_screen,
)


def cmd_run(out_dir: Path, cache_dir: str) -> None:
    prereg = out_dir / "PREREGISTRATION.md"
    if not prereg.exists():
        raise SystemExit(
            f"no frozen pre-registration at {prereg}; the design must be frozen before any data look"
        )
    now_ms = int(time.time() * 1000)
    bundle = load_bundle(BTC_ASSET, START_MS, now_ms, cache_dir)
    result = run_screen(bundle)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdict.md").write_text(render_verdict(result))
    status = "PASS" if result["verdict"]["passed"] else "CLOSED_NEGATIVE"
    print(f"[{status}] {result['verdict']['reason']}")
    print(f"verdict -> {out_dir / 'verdict.md'}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/lane1_twap")
    sub = p.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run the frozen Track-A screen")
    run_p.add_argument("--cache-dir", default=".backtest_cache")
    args = p.parse_args()
    if args.command == "run":
        cmd_run(Path(args.out), args.cache_dir)


if __name__ == "__main__":
    main()
