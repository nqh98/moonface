from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HypothesisSpec:
    """One pre-registered hypothesis: entry x exit x asset x sizing fraction.

    Frozen and hashable by content: the sha256 of the canonical JSON is the
    idempotency key in the store. dict fields are never mutated after creation."""

    domain: str
    version: int
    asset: dict     # {"exchange","symbol","timeframe"} (+ "funding_symbol"/"spot_symbol")
    entry: dict     # {"family": str, "params": dict}
    exit: dict      # {"name": str, "params": dict}
    fraction: float

    def __eq__(self, other) -> bool:
        if not isinstance(other, HypothesisSpec):
            return NotImplemented
        return canonical_json(self) == canonical_json(other)

    def __hash__(self) -> int:
        return hash(canonical_json(self))


def canonical_json(spec: HypothesisSpec) -> str:
    return json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))


def spec_hash(spec: HypothesisSpec) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()


def spec_from_json(text: str) -> HypothesisSpec:
    return HypothesisSpec(**json.loads(text))
