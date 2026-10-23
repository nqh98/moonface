#!/usr/bin/env python
# tools/accrual_check.py
"""Is anything actually accruing? One command, non-zero exit when it is not.

Every remaining route to a credible signal depends on data collected between
now and ~2027 (see docs/findings/MANDATE_ASSESSMENT_2026-07.md addendum). On
2026-07-29 all three streams were found dead or empty, after 16, 20 and 26 days
of nobody looking. This is the check that would have caught all three the same
day.

  .venv/bin/python tools/accrual_check.py            # human-readable table
  .venv/bin/python tools/accrual_check.py --json     # machine-readable

Exit 0 = every stream fresh. Exit 1 = at least one STALE or NO_OUTPUT. Safe to
run from cron; it reads files only and never touches a registration, a journal
or a frozen lane.

Suggested supervision (adjust the mail/notify step to taste):

  0 * * * * cd <repo> && .venv/bin/python tools/accrual_check.py \
      || echo "MoonFace: a collection stream is not accruing" | \
         mail -s "accrual alert" you@example.com
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.accrual import (newest_ts_from_jsonl,
                                       newest_ts_from_manifest,
                                       stream_status, worst_status)

# name -> (kind, path, field-or-None, max_age_hours, why this threshold)
STREAMS = [
    ("confluence_v2.2_journal", "jsonl", "journal/signals.jsonl", "candle_ts_ms",
     12.0, "1h candles (promotion/engine.json): 12h = 12 missed closes,"
           " tolerant of a transient fetch outage but not of a dead daemon"),
    ("liquidations_usdm", "manifest",
     "experiments/newdata/liquidations/manifest.json", None,
     72.0, "BTCUSDT-scoped and genuinely sparse; a real gap can exceed a day"),
    ("deribit_options_chain", "manifest",
     "experiments/newdata/deribit_chain/manifest.json", None,
     48.0, "daily cadence: 48h = two consecutive missed snapshots"),
]


def collect(root: Path, now_ms: int) -> list:
    out = []
    for name, kind, rel, field, max_age, _why in STREAMS:
        path = root / rel
        if kind == "jsonl":
            last = newest_ts_from_jsonl(path, field)
        else:
            last = newest_ts_from_manifest(path)
        out.append(stream_status(name, last, now_ms, max_age))
    return out


def _render(statuses: list, overall: str) -> str:
    lines = [f"{'stream':26s} {'level':10s} {'age':>10s} {'limit':>8s}",
             "-" * 58]
    for s, (_n, _k, _r, _f, _m, why) in zip(statuses, STREAMS):
        age = "never" if s.age_hours is None else f"{s.age_hours:.1f}h"
        lines.append(f"{s.name:26s} {s.level:10s} {age:>10s}"
                     f" {s.max_age_hours:>7.0f}h")
        if s.stale:
            lines.append(f"{'':26s}   threshold rationale: {why}")
    lines += ["", f"overall: {overall}"]
    if overall != "OK":
        lines.append("NO_OUTPUT = never produced a row (shipped/scheduled but"
                     " not working). STALE = fell behind.")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".", help="repository root")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.add_argument("--now-ms", type=int, default=None,
                   help="override the clock (testing)")
    args = p.parse_args()
    now = int(time.time() * 1000) if args.now_ms is None else args.now_ms
    statuses = collect(Path(args.root), now)
    overall = worst_status(statuses)
    if args.as_json:
        print(json.dumps({
            "overall": overall,
            "now_ms": now,
            "streams": [{"name": s.name, "level": s.level,
                         "last_ts_ms": s.last_ts_ms,
                         "age_hours": (None if s.age_hours is None
                                       else round(s.age_hours, 2)),
                         "max_age_hours": s.max_age_hours}
                        for s in statuses]}, indent=2))
    else:
        print(_render(statuses, overall))
    raise SystemExit(0 if overall == "OK" else 1)


if __name__ == "__main__":
    main()
