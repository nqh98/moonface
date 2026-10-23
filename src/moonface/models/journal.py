"""Append-only JSONL log: one journal entry per line, fsync'd. Generic --
this module has no v2.2 or engine-specific coupling. Split out of
signal/journal.py at G5; the promotion-gate half (forward_report) was
v2.2-specific and was deleted with the rest of the v2.2 runtime, not moved
here."""
from __future__ import annotations

import json
import os
from pathlib import Path


def append_entry(path: str | Path, record: dict) -> None:
    """Append-only with fsync; records are never rewritten in place."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_entries(path: str | Path) -> list[dict]:
    """A corrupt trailing line (torn write) is quarantined to a sidecar file;
    corruption anywhere else is a real error and raises."""
    p = Path(path)
    if not p.exists():
        return []
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    out: list[dict] = []
    for idx, line in enumerate(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            if idx == len(lines) - 1:
                with open(str(p) + ".quarantine", "a") as q:
                    q.write(line + "\n")
                break
            raise ValueError(f"corrupt journal line {idx + 1} in {p}")
    return out
