#!/usr/bin/env python
"""vrp_measure one-time DVOL fetch. RUN ONCE, BY HAND.

Fetches the full Deribit BTC DVOL history to
cache/exogenous/dvol_BTC_43200_full.csv. Does NOT touch
cache/exogenous/dvol_BTC_43200.csv -- that is a frozen `exogenous` lane
artifact (SPEC vrp_measure section 3).

Expected: 3837 points, 2021-03-24 -> 2026-06-24. Hard-fails on any cadence
gap or a span under 1900 days -- stop and ask, do not work around it.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from moonface.research.exogenous.deribit_dvol import DvolPoint, fetch_dvol  # noqa: E402

RESOLUTION = 43200
RESOLUTION_MS = RESOLUTION * 1000
DAY_MS = 86_400_000
MIN_SPAN_DAYS = 1900
OUT_DIR = REPO / "cache/exogenous"
OUT_NAME = "dvol_BTC_43200_full.csv"
FETCH_START_MS = 1_483_228_800_000   # 2017-01-01, safely before DVOL inception
FETCH_END_MS = 1_782_259_200_000     # 2026-06-24 00:00 UTC (SPEC section 3.2)


class GapError(ValueError):
    """The fetched DVOL series is not a contiguous 12h cadence."""


def drop_incomplete_tail(points: list[DvolPoint], now_ms: int,
                         interval_ms: int = RESOLUTION_MS) -> list[DvolPoint]:
    """Drop trailing bars still forming. A bar stamped t is complete only once
    now >= t + interval (the API serves the current, partial bar)."""
    return [p for p in points if p.ts_ms + interval_ms <= now_ms]


def check_cadence(points: list[DvolPoint], interval_ms: int = RESOLUTION_MS) -> None:
    """Strict `interval_ms` spacing, ascending. Raises GapError otherwise."""
    if len(points) < 2:
        raise GapError(f"need >= 2 points, got {len(points)}")
    for prev, cur in zip(points, points[1:]):
        step = cur.ts_ms - prev.ts_ms
        if step != interval_ms:
            raise GapError(f"{step} ms step after {prev.ts_ms} (want {interval_ms})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default=str(OUT_DIR))
    parser.add_argument("--start-ms", type=int, default=FETCH_START_MS)
    parser.add_argument("--end-ms", type=int, default=FETCH_END_MS)
    args = parser.parse_args(argv)

    out = Path(args.cache_dir) / OUT_NAME
    if out.exists():
        print(f"REFUSING: {out} exists (one-time fetch; delete deliberately to redo)")
        return 1

    tmp_dir = Path(args.cache_dir) / "_vrp_fetch_tmp"
    points = fetch_dvol("BTC", args.start_ms, args.end_ms, str(tmp_dir),
                        resolution=RESOLUTION)
    points = drop_incomplete_tail(points, now_ms=int(time.time() * 1000))
    check_cadence(points)

    span_days = (points[-1].ts_ms - points[0].ts_ms) / DAY_MS
    if span_days < MIN_SPAN_DAYS:
        print(f"STOP-AND-ASK: span {span_days:.1f}d < {MIN_SPAN_DAYS}d "
              f"({len(points)} points). Do not proceed.")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        for p in points:
            fh.write(f"{p.ts_ms},{p.open},{p.high},{p.low},{p.close}\n")
    print(f"wrote {out}: {len(points)} points, span {span_days:.1f}d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
