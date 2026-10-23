from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class JournalEvent:
    journal_id: str
    timestamp_ms: int
    status: str
    regime: str
    setup: str | None
    confirm_2h: bool
    indicators: dict
    entry: float | None
    stop: float | None
    exit_rule: str
    risk_r: float | None
    reason: str
    invalidation_reason: str | None
    final_r: float | None
    mae_r: float | None
    mfe_r: float | None
    outcome_class: str | None

    def to_dict(self) -> dict:
        return asdict(self)


REQUIRED_FIELDS = tuple(f.name for f in fields(JournalEvent))


def write_jsonl(events: list[JournalEvent], path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        for e in events:
            fh.write(json.dumps(e.to_dict()) + "\n")
