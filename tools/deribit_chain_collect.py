#!/usr/bin/env python
"""Deribit BTC options-chain daily snapshot collector CLI.

Forward-collect lane (option A of the Deribit Stage-0 feasibility verdict):
`collect` appends at most one whole-chain snapshot per UTC day; `status`
prints collection stats and the current newdata readiness-gate assessment.
Data acquisition only — no signal or alpha work happens here.

Run from cron. The collector is idempotent per cadence bucket and does NOT
make a network call inside an already-collected bucket, so running it every
minute is safe and self-healing after a reboot or a missed tick:

  * * * * * cd <repo> && flock -n /tmp/deribit_chain.lock \
      .venv/bin/python tools/deribit_chain_collect.py collect >> watch.log 2>&1

Default cadence is HOURLY. Sub-daily data downsamples to daily; daily cannot be
upsampled, so a daily archive can never test an intraday dealer-hedging
hypothesis. Changing cadence after accrual starts resets the readiness clock --
decide once, before the first snapshot.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.collect.deribit_chain import (DEFAULT_CADENCE_MS, HOUR_MS,
                                            collect_once, csv_path,
                                            snapshot_stats)
from moonface.research.newdata import assess_manifest, load_manifest


def cmd_collect(out_dir: Path, currency: str,
                cadence_ms: int = DEFAULT_CADENCE_MS) -> int:
    result = collect_once(out_dir, currency, cadence_ms=cadence_ms)
    s = result["stats"]
    print(f"[{result['status']}] {result['date']} appended={result['appended']} "
          f"skipped={result['skipped']}")
    print(f"days={s['days']} history_days={s['history_days']} "
          f"coverage={s['coverage_ratio']:.4f} rows={s['rows']} "
          f"buckets={s.get('buckets', 0)} "
          f"bucket_coverage={s.get('bucket_coverage_ratio', 0.0):.4f}")
    return 0 if result["status"] in ("collected", "already_collected") else 1


def cmd_status(out_dir: Path, currency: str,
               cadence_ms: int = DEFAULT_CADENCE_MS) -> int:
    stats = snapshot_stats(csv_path(out_dir, currency), cadence_ms)
    print(json.dumps(stats, indent=2))
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print("no manifest yet; run `collect` first")
        return 1
    verdict = assess_manifest(load_manifest(manifest_path))
    print(f"readiness: {verdict['status']}")
    for failure in verdict["failures"]:
        print(f"  - {failure}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/newdata/deribit_chain")
    p.add_argument("--currency", default="BTC")
    p.add_argument("--cadence-hours", type=float, default=HOUR_MS / 3_600_000,
                   help="collect at most one snapshot per this many hours"
                        " (default 1; use 24 for the old daily behaviour)."
                        " Changing this after accrual starts resets the"
                        " readiness clock -- decide once.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("collect",
                   help="append a snapshot (idempotent per cadence bucket)")
    sub.add_parser("status", help="print collection stats and readiness assessment")
    args = p.parse_args()
    out_dir = Path(args.out)
    cadence_ms = max(1, int(args.cadence_hours * 3_600_000))
    if args.command == "collect":
        raise SystemExit(cmd_collect(out_dir, args.currency, cadence_ms))
    raise SystemExit(cmd_status(out_dir, args.currency, cadence_ms))


if __name__ == "__main__":
    main()
