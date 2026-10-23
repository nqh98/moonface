#!/usr/bin/env python3
"""Bollinger-breakout harvest CLI (research). Resolves the CI-clean bb_breakout
drift through the frozen 3-stage edge_search gate with real exits, cost, an OOS
holdout split, and the economic bar. Writes a JSON result + markdown verdict.
No promotion; an EDGE here is paper-only and the WAIT stance is unchanged."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent))                # import tools.engine.smc_decompose
sys.path.insert(0, str(_HERE.parent.parent / "src"))        # import moonface.*

from moonface.research.bb_harvest import (  # noqa: E402
    render_report, run,
)
from tools.engine.smc_decompose import _load_candles  # noqa: E402


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="BTC/USDT:USDT")
    p.add_argument("--tf", choices=["1h", "4h"], default="4h")
    p.add_argument("--start-ms", type=int, default=1_577_836_800_000)  # 2020-01-01
    p.add_argument("--end-ms", type=int, default=2_000_000_000_000)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", default="experiments/bb_harvest")
    p.add_argument("--holdout-bars", type=int, default=2190,  # ~1y of 4h bars
                   help="bars reserved from stage 1/2; stage 3 still sees full")
    p.add_argument("--from-1h", action="store_true", default=True)
    args = p.parse_args(argv)

    full = _load_candles(args)
    if len(full) <= args.holdout_bars:
        print(f"FEASIBILITY FAIL: {len(full)} bars <= holdout {args.holdout_bars}")
        sys.exit(1)
    train_oos = full[:-args.holdout_bars]

    rows = run(train_oos, full)
    report = render_report(rows, args.symbol, args.tf, len(full), args.holdout_bars)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"results_{args.tf}.json").write_text(json.dumps(rows, indent=2))
    (out_dir / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
