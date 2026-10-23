# src/moonface/research/accrual.py
"""Liveness check for every forward-collecting stream in the program.

Written after the third occurrence of the same failure
(`experiments/COLLECTOR_AUDIT_2026-07-29.md`): a collector is shipped or
scheduled, everyone believes a clock is running toward a 2027 readiness gate,
and nothing is actually accruing. It cost 16 days (liquidations), 26 days
(Deribit chain) and 20 days (the confluence v2.2 forward record) before anyone
looked.

The durable fix is not "remember to install the cron" — that instruction has now
failed twice. It is to make the failure **loud and cheap to detect**: read the
OUTPUT of each stream, never its process table, and fail with a non-zero exit so
a supervisor or a human running one command sees it the same day.

Pure module: no IO beyond reading the files it is pointed at, no network, no
clock of its own (`now_ms` is always injected so the checks are testable)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_HOUR_MS = 3_600_000

# Worst-first. NO_OUTPUT is deliberately distinct from STALE: a stream that has
# never produced a row cannot be caught by an age threshold, and that is exactly
# the shape all three real failures took.
_SEVERITY = ("NO_OUTPUT", "STALE", "OK")


@dataclass(frozen=True)
class StreamStatus:
    name: str
    last_ts_ms: int | None
    age_hours: float | None
    max_age_hours: float
    stale: bool
    level: str


def stream_status(name: str, last_ts_ms: int | None, now_ms: int,
                  max_age_hours: float) -> StreamStatus:
    """Classify one stream. `last_ts_ms is None` means the stream has produced
    nothing at all — reported as NO_OUTPUT rather than as an infinite age,
    because "never started" and "fell behind" need different responses."""
    if last_ts_ms is None:
        return StreamStatus(name, None, None, max_age_hours, True, "NO_OUTPUT")
    age = max(0.0, (now_ms - last_ts_ms) / _HOUR_MS)
    stale = age > max_age_hours
    return StreamStatus(name, last_ts_ms, age, max_age_hours, stale,
                        "STALE" if stale else "OK")


def worst_status(statuses: list[StreamStatus]) -> str:
    """The most severe level present; OK when there is nothing to report."""
    for level in _SEVERITY:
        if any(s.level == level for s in statuses):
            return level
    return "OK"


def newest_ts_from_jsonl(path: Path, field: str) -> int | None:
    """Largest `field` across every row of a JSONL file, or None when the file
    is absent or holds no usable row. Takes the max rather than the tail: a
    restart can append out of order, and a tail read would then report a
    healthy stream as stale."""
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    best: int | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            val = json.loads(line).get(field)
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(val, int) and (best is None or val > best):
            best = val
    return best


def newest_ts_from_manifest(path: Path) -> int | None:
    """`collection.last_ts_ms` from a collector manifest, or None when the file
    is absent or the collector has written zero rows.

    The zero-rows case must NOT fall through as a timestamp of 0 — that is
    precisely the liquidation collector's 16-day state (manifest present,
    well-formed, `rows: 0`), and reading it as an age of ~56 years would look
    like a different bug than the one it is."""
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    coll = payload.get("collection") or {}
    if not coll.get("rows"):
        return None
    ts = coll.get("last_ts_ms")
    return ts if isinstance(ts, int) and ts > 0 else None
