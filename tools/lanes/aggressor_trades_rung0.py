#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.aggressor_trades import (
    BUCKET_MS,
    load_trade_csv,
    render_report,
    run_nonlockbox_rung0,
)


def cmd_nonlockbox(csv_path: Path, out_dir: Path) -> dict:
    result_path = out_dir / "nonlockbox_results.json"
    if result_path.exists():
        sys.exit(f"{result_path} already exists; Rung-0 non-lockbox assessment is one-touch")
    trades = load_trade_csv(csv_path)
    result = run_nonlockbox_rung0(trades, cadence_ms=BUCKET_MS)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit.json").write_text(json.dumps(result["audit"], indent=2) + "\n")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    (out_dir / "report.md").write_text(render_report(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen aggressor-trades Rung-0 non-lockbox test.")
    parser.add_argument("--csv", required=True, help="Path to per-second aggressor CSV with ts_ms,symbol,buy_count,sell_count,last_price")
    parser.add_argument("--out", required=True, help="Output directory for Rung-0 artifacts")
    parser.add_argument(
        "--open-lockbox",
        action="store_true",
        help="Always refused in this implementation plan; lockbox opening requires a separate approval.",
    )
    args = parser.parse_args()
    if args.open_lockbox:
        sys.exit("lockbox opening is not implemented; obtain explicit approval in a separate plan")
    result = cmd_nonlockbox(Path(args.csv), Path(args.out))
    print(f"[{result['status']}] lockbox_touched={str(result['lockbox_touched']).lower()}")


if __name__ == "__main__":
    main()
