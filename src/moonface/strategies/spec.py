from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

VALID_STATUSES = {"paper", "live"}


@dataclass(frozen=True)
class PromotedStrategy:
    """The single source of truth for what moonface-signal may emit.
    Promotion paper -> live is a human git commit, never automatic."""

    family: str
    params: dict
    exit: dict          # {"name": str, "params": dict with "atr_period"}
    fraction: float
    status: str         # "paper" | "live"
    asset: dict         # {"exchange","symbol","timeframe"} (+ data legs)
    provenance: dict    # research domain/version/spec_hash/report paths
    max_drawdown_p95: float


def load_strategy(path: str | Path) -> PromotedStrategy | None:
    """Fail-safe loader: missing file, parse error, or schema violation all
    return None — the CLI then behaves as if no strategy exists."""
    from moonface.core.exits import EXECUTABLE_EXITS
    from moonface.strategies.registry import get_strategy_module

    try:
        raw = json.loads(Path(path).read_text())
        s = PromotedStrategy(**raw)
    except (OSError, ValueError, TypeError):
        return None
    module = get_strategy_module(s.family)
    if (s.status not in VALID_STATUSES
            or module is None
            or not isinstance(s.params, dict)
            or not isinstance(s.exit, dict)
            or s.exit.get("name") not in EXECUTABLE_EXITS
            or not isinstance(s.exit.get("params"), dict)
            or "atr_period" not in s.exit["params"]
            or not isinstance(s.fraction, (int, float)) or s.fraction <= 0
            or not isinstance(s.asset, dict)
            or not isinstance(s.max_drawdown_p95, (int, float))
            or s.max_drawdown_p95 <= 0
            or not module.validate(s)):
        return None
    return s


def strategy_hash(s: PromotedStrategy) -> str:
    """Identity of the signal-relevant content. status/provenance excluded so
    a paper->live flip does not start a new journal segment."""
    payload = {"family": s.family, "params": s.params, "exit": s.exit,
               "fraction": s.fraction, "asset": s.asset}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
