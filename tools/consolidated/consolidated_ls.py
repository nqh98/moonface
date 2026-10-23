#!/usr/bin/env python3
"""Consolidated leaderboard CLI: --run drives runner.run + report render + write."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))  # so `from tools.engine.engine_backtest import ...` resolves

from moonface.research.consolidated.report import render_json, render_markdown  # noqa: E402
from moonface.research.consolidated.runner import run  # noqa: E402

_DEFAULT_OUT_DIR = "experiments/consolidated_ls"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Consolidated diagnostic-re-rank leaderboard."
    )
    parser.add_argument("--run", action="store_true", help="Run pipeline and write report.")
    parser.add_argument("--start-ms", type=int, default=1577836800000)
    parser.add_argument("--end-ms", type=int, default=1782300000000)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--out-dir", default=None)

    args = parser.parse_args(argv)

    if not args.run:
        parser.print_help()
        return

    explicit_out = args.out_dir is not None
    out_dir = Path(args.out_dir) if args.out_dir else Path(_DEFAULT_OUT_DIR)

    if not explicit_out:
        # Refuse to write outside experiments/consolidated_ls unless --out-dir given
        try:
            out_dir.resolve().relative_to(Path(_DEFAULT_OUT_DIR).resolve())
        except ValueError:
            print(
                f"error: default out-dir would resolve outside {_DEFAULT_OUT_DIR}; "
                "pass --out-dir explicitly to override",
                file=sys.stderr,
            )
            sys.exit(1)

    result = run(args.start_ms, args.end_ms, args.cache_dir)
    asof = date.today().isoformat()

    md = render_markdown(result, asof)
    js = render_json(result, asof)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "LEADERBOARD.md").write_text(md, encoding="utf-8")
    (out_dir / "RESULT.json").write_text(json.dumps(js, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
